from sqlalchemy import (Boolean, Column, DateTime, Integer, MetaData, String,
                        Table, create_engine, text)


def main():
    engine = create_engine("sqlite:///report_catalog.db")
    metadata = MetaData()

    table_define = Table(  # noqa: F841
        "report_catalog",
        metadata,
        Column("id", Integer, primary_key = True),
        Column("test_case", String, index = True, nullable = False),
        Column("file_name", String, unique = True, nullable = False),
        Column("created_at", DateTime, server_default = text("CURRENT_TIMESTAMP"), nullable = False),
        Column("is_deleted", Boolean, server_default = text("0"), nullable = False),
    )

    metadata.create_all(engine)

    print("finished")

if __name__ == "__main__":
    main()