import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import get_current_user
from backend.database import Base
from backend.models import ContextDocument
from backend.routers.context import router
from backend.services import document_uploads as service
from backend.services.document_parser import ParserUnavailable
from backend.services.upload_progress import UploadProgress


class DocumentUploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'))
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.store = UploadProgress()
        self.open_sessions = 0

        @contextmanager
        def sessions():
            self.open_sessions += 1
            try:
                with self.sessions() as db:
                    yield db
            finally:
                self.open_sessions -= 1

        self.manager = service.DocumentUploads(self.store, sessions, workers=2, capacity=3)
        await self.manager.start()

    async def asyncTearDown(self):
        await self.manager.shutdown()
        self.engine.dispose()
        self.temp.cleanup()

    async def submit(self, content=b'pdf', filename='manual.pdf'):
        key = self.store.create('admin')
        await self.manager.submit(key, 'admin', content=content, filename=filename, title=None, device_id=None)
        return key

    async def test_bounded_workers_release_sessions_during_inference_and_clean_files(self):
        started = asyncio.Event()
        release = asyncio.Event()
        active = maximum = 0

        async def parse(content, extension, progress):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                started.set()
            progress('parsing', 0, 1)
            await release.wait()
            active -= 1
            progress('parsing', 1, 1)
            return 'Maintenance instructions for the cooling fans.'

        with patch.object(service, 'parse_document_async', side_effect=parse):
            keys = [await self.submit(content=f'pdf {n}'.encode()) for n in range(3)]
            await asyncio.wait_for(started.wait(), 2)
            self.assertEqual(self.open_sessions, 0)
            self.assertEqual(self.store.get(keys[2], 'admin')['phase'], 'queued')
            with self.assertRaises(ParserUnavailable):
                await self.submit(content=b'full queue')
            self.assertEqual(len(list(Path(self.manager._directory.name).iterdir())), 3)
            release.set()
            await asyncio.wait_for(self.manager._queue.join(), 2)
        self.assertEqual(maximum, 2)
        self.assertEqual(self.open_sessions, 0)
        for key in keys:
            self.assertEqual(self.store.get(key, 'admin')['phase'], 'complete')
        with self.sessions() as db:
            self.assertEqual(db.query(ContextDocument).count(), 3)
        self.assertEqual(list(Path(self.manager._directory.name).iterdir()), [])
        self.assertEqual(self.manager._pending, 0)

    async def test_failure_does_not_kill_worker_or_save_partial_document(self):
        async def parse(content, extension, progress):
            progress('parsing', 1, 2)
            raise ParserUnavailable('Parser timed out on page 2. No document was saved.')

        with patch.object(service, 'parse_document_async', side_effect=parse):
            key = await self.submit()
            await asyncio.wait_for(self.manager._queue.join(), 2)
        self.assertEqual(self.store.get(key, 'admin')['phase'], 'failed')
        with self.sessions() as db:
            self.assertEqual(db.query(ContextDocument).count(), 0)
        text_key = await self.submit(b'Maintenance instructions for the cooling fans.', 'manual.txt')
        await asyncio.wait_for(self.manager._queue.join(), 2)
        self.assertEqual(self.store.get(text_key, 'admin')['phase'], 'complete')
        self.assertEqual(list(Path(self.manager._directory.name).iterdir()), [])

    async def test_shutdown_cancels_active_and_queued_work_without_saving(self):
        entered = asyncio.Event()

        async def parse(*args):
            entered.set()
            await asyncio.Event().wait()

        with patch.object(service, 'parse_document_async', side_effect=parse):
            keys = [await self.submit(f'pdf {n}'.encode()) for n in range(3)]
            await asyncio.wait_for(entered.wait(), 2)
            directory = Path(self.manager._directory.name)
            await asyncio.wait_for(self.manager.shutdown(), 2)
        self.assertFalse(directory.exists())
        self.assertEqual(self.manager._pending, 0)
        for key in keys:
            self.assertEqual(self.store.get(key, 'admin')['phase'], 'failed')
        with self.sessions() as db:
            self.assertEqual(db.query(ContextDocument).count(), 0)

    async def test_simultaneous_duplicate_uploads_save_only_once(self):
        async def parse(*args):
            await asyncio.sleep(0.01)
            return 'Maintenance instructions for the cooling fans.'

        with patch.object(service, 'parse_document_async', side_effect=parse):
            keys = [await self.submit() for _ in range(2)]
            await asyncio.wait_for(self.manager._queue.join(), 2)
        self.assertEqual(sorted(self.store.get(key, 'admin')['phase'] for key in keys), ['complete', 'failed'])
        with self.sessions() as db:
            self.assertEqual(db.query(ContextDocument).count(), 1)


class QueuedUploadRouteTests(unittest.TestCase):
    def test_accepted_response_precedes_inference_completion_and_retries_do_not_duplicate(self):
        store = UploadProgress()
        manager = service.DocumentUploads(store, workers=1)
        entered = threading.Event()

        async def process(work):
            store.update(work.upload_id, 'parsing', 0, 1)
            entered.set()
            await asyncio.Event().wait()

        @asynccontextmanager
        async def lifespan(app):
            await manager.start()
            try:
                yield
            finally:
                await manager.shutdown()

        app = FastAPI(lifespan=lifespan)
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: 'admin'
        with patch('backend.routers.context.uploads', store), patch('backend.routers.context.document_uploads', manager), patch.object(manager, '_process', side_effect=process), TestClient(app) as client:
            key = client.post('/api/v2/context/uploads').json()['upload_id']
            response = client.post(f'/api/v2/context/uploads/{key}/file', files={'file': ('manual.pdf', b'pdf')})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertTrue(entered.wait(2))
            self.assertEqual(client.get(f'/api/v2/context/uploads/{key}').json()['phase'], 'parsing')
            repeat = client.post(f'/api/v2/context/uploads/{key}/file', files={'file': ('manual.pdf', b'pdf')})
            self.assertEqual(repeat.status_code, 202)
            self.assertEqual(manager._pending, 1)
            app.dependency_overrides[get_current_user] = lambda: 'other'
            self.assertEqual(client.post(f'/api/v2/context/uploads/{key}/file', files={'file': ('manual.pdf', b'pdf')}).status_code, 404)
