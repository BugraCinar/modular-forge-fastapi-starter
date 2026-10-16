def install(app, runtime):
    from modular_forge.kafka.service import KafkaEvents

    runtime.events = KafkaEvents(runtime.settings)
    runtime.closers.append(runtime.events.close)
