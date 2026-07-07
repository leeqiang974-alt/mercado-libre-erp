def import_all_models() -> None:
    import app.models.audit_event  # noqa: F401
    import app.models.product_draft  # noqa: F401
    import app.models.publish_job  # noqa: F401
    import app.models.review_result  # noqa: F401
    import app.models.source_product  # noqa: F401
    import app.models.store  # noqa: F401
    import app.models.token_credential  # noqa: F401
