def register(name):
    from apps.email import definitions

    def _email_definition_wrapper(email_def):
        definitions.register(name, email_def)
        return email_def

    return _email_definition_wrapper
