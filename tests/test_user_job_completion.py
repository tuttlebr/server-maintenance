import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device, ManagedUser, UserHostAssociation
from backend.services.ansible_runner import _apply_completion_action


class UserJobCompletionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        db = self.session_factory()
        db.add_all([
            Device(hostname="node-01", transport="ssh"),
            Device(hostname="node-02", transport="ssh"),
        ])
        db.commit()
        db.close()
        self.session_patch = patch(
            "backend.services.ansible_runner.SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()

    def test_provision_state_is_applied_as_a_completion_action(self):
        _apply_completion_action({
            "type": "provision_users",
            "hostnames": ["node-01"],
            "users": [{"username": "juser", "full_name": "Jane User", "email": "juser@example.com"}],
        })
        db = self.session_factory()
        managed = db.query(ManagedUser).filter_by(username="juser").one()
        self.assertEqual(managed.groups, "users")
        self.assertEqual(db.query(UserHostAssociation).filter_by(user_id=managed.id).count(), 1)
        db.close()

    def test_partial_removal_preserves_remaining_associations(self):
        _apply_completion_action({
            "type": "provision_users",
            "hostnames": ["node-01", "node-02"],
            "users": [{"username": "juser", "full_name": "Jane User", "email": "juser@example.com"}],
        })
        _apply_completion_action({
            "type": "remove_user",
            "hostnames": ["node-01"],
            "username": "juser",
        })
        db = self.session_factory()
        managed = db.query(ManagedUser).filter_by(username="juser").one()
        self.assertEqual(db.query(UserHostAssociation).filter_by(user_id=managed.id).count(), 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
