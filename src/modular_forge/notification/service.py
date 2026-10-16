import smtplib
import ssl
from email.message import EmailMessage

from modular_forge.shared.errors import unavailable


class SMTPNotifications:
    def __init__(self, settings):
        self.settings = settings

    def send(self, recipient, subject, text):
        message = EmailMessage()
        message["From"] = self.settings.mail_sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        try:
            with smtplib.SMTP(self.settings.mail_host, self.settings.mail_port, timeout=10) as smtp:
                smtp.ehlo()
                if self.settings.mail_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if self.settings.mail_username:
                    smtp.login(self.settings.mail_username, self.settings.mail_password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError):
            raise unavailable() from None
