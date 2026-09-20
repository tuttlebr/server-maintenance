"""Reconcile observations, never inferred privilege from a requested action."""
from datetime import datetime, timezone
from backend.models import Host, ManagedUser, UserHostAssociation


def reconcile_accounts(db, reports, targets):
    hosts = {host.hostname: host for host in db.query(Host).filter(Host.hostname.in_(targets)).all()}
    for report in reports:
        if report.get('report_type') != 'accounts' or report.get('hostname') not in hosts:
            continue
        host = hosts[report['hostname']]
        for record in report.get('accounts', []):
            username = record.get('username', '')
            if not username or not isinstance(record.get('present'), bool):
                continue
            user = db.query(ManagedUser).filter_by(username=username).first()
            if not user:
                user = ManagedUser(username=username)
                db.add(user)
                db.flush()
            association = db.query(UserHostAssociation).filter_by(user_id=user.id, host_id=host.id).first()
            if not association:
                association = UserHostAssociation(user_id=user.id, host_id=host.id)
                db.add(association)
            association.groups = ','.join(record.get('groups', []))
            association.shell = record.get('shell')
            association.managed_sudo = record.get('managed_sudo')
            association.sudo_policy = record.get('sudo_policy')
            association.state = 'observed' if record['present'] else 'absent'
            association.observed_at = datetime.now(timezone.utc)
    db.commit()
