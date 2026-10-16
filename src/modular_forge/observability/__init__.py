def install(app, runtime):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=runtime.settings.sentry_dsn,
        environment=runtime.settings.environment,
        send_default_pii=False,
        traces_sample_rate=0.05,
        include_local_variables=False,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        before_send=scrub_event,
        before_send_transaction=scrub_event,
    )


def scrub_event(event, hint):
    event.pop("request", None)
    event.pop("user", None)
    event.pop("breadcrumbs", None)
    # Exception values can contain driver parameters or submitted credentials.
    for value in event.get("exception", {}).get("values", []):
        value["value"] = "Exception details redacted"
    return event
