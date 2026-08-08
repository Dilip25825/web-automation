import hashlib
import secrets

from django.core.management.base import BaseCommand, CommandError

from licensing.models import ErpApiClientToken


class Command(BaseCommand):
    help = 'Issue or rotate one revocable ERP API token for an OperatorMobile.'

    def add_arguments(self, parser):
        parser.add_argument('operator_mobile')

    def handle(self, *args, **options):
        mobile = ''.join(filter(str.isdigit, str(options['operator_mobile'])))
        if len(mobile) == 12 and mobile.startswith('91'):
            mobile = mobile[2:]
        if len(mobile) != 10 or mobile[0] not in '6789':
            raise CommandError('Valid 10 digit Indian OperatorMobile required hai.')

        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        credential, created = ErpApiClientToken.objects.update_or_create(
            operator_mobile=mobile,
            defaults={
                'token_hash': token_hash,
                'token_prefix': raw_token[:12],
                'is_active': True,
                'expires_at': None,
                'last_used_at': None,
            },
        )
        action = 'issued' if created else 'rotated'
        self.stdout.write(self.style.SUCCESS(f'ERP API token {action} for {mobile}.'))
        self.stdout.write('Copy this token now; database me sirf hash store hua hai:')
        self.stdout.write(raw_token)