from django.core.mail.backends.base import BaseEmailBackend


class BrokenBackend(BaseEmailBackend):
    """Simulates an SMTP outage."""

    def send_messages(self, email_messages):
        raise ConnectionError("simulated SMTP outage")
