"""Reconcile observations, never inferred privilege from a requested action."""
from datetime import datetime, timezone
from backend.models import Host, ManagedUser, UserHostAssociation


def reconcile_accounts(db, reports, targets):
    hosts = {host.hostname: host for host in db.query(Host).filter(Host.hostname.in_(targets)).all()}
    for report in reports:
        if report.get('report_type') != 'accounts' or report.get('hostname') not in hosts:
            continue
        host = hosts[report['hostname']]
        records = report.get('accounts')
        if not isinstance(records, list):
            continue
        observed_at = datetime.now(timezone.utc)
        observed_ids = set()
        complete = report.get('scope') == 'all'
        for record in records:
            if not isinstance(record, dict):
                complete = False
                continue
            username = record.get('username', '')
            if not isinstance(username, str) or not username or not isinstance(record.get('present'), bool):
                complete = False
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
            observed_ids.add(user.id)
            association.full_name = record.get('full_name')
            association.uid = record.get('uid')
            association.home = record.get('home')
            association.groups = ','.join(record.get('groups', []))
            association.shell = record.get('shell')
            association.managed_sudo = record.get('managed_sudo')
            association.sudo_policy = record.get('sudo_policy')
            association.state = 'observed' if record['present'] else 'absent'
            association.observed_at = observed_at
        if complete:
            # Only a full inventory can prove an account disappeared. Targeted
            # reports after edits must leave unrelated accounts untouched.
            for association in db.query(UserHostAssociation).filter_by(host_id=host.id).all():
                if association.user_id not in observed_ids:
                    association.state = 'absent'
                    association.managed_sudo = None
                    association.sudo_policy = None
                    association.observed_at = observed_at
    db.commit()
