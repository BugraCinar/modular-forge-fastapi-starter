from modular_forge.notification.service import SMTPNotifications


def install(app, runtime):
    runtime.notifications = SMTPNotifications(runtime.settings)
