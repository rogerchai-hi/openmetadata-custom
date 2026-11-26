import os
import sqlite3
from datetime import date, datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TypeAlias, cast
from zoneinfo import ZoneInfo

import pandas as pd
from dateutil import parser
from evidently import Report
from evidently.legacy.tests.base_test import TestStatus
from evidently.metrics import ValueDrift
from metadata.data_quality.validations.base_test_handler import \
    BaseTestValidator
from metadata.generated.schema.tests.basic import (TestCaseResult,
                                                   TestResultValue)
from metadata.utils.entity_link import get_decoded_column
from sqlalchemy import inspect, select

if TYPE_CHECKING:
    from evidently.core.report import Snapshot
    from metadata.profiler.processor.runner import QueryRunner
    from sqlalchemy import Column
    SupportedColType: TypeAlias = int | str | date | datetime

class DatadriftValidator(BaseTestValidator):
    report_dir = Path("/datadrift_report")
    max_report = 5

    @cached_property
    def report_name(self):
        ts = self.execution_date.root // 1000
        test_name = self.test_case.name.root

        return f"{test_name}_{ts}"

    def _report_output_2_test_case_result(self, snapshot: "Snapshot") -> TestCaseResult:
        payload = snapshot.dict()
        def is_passed(status: TestStatus) -> bool:
            return status in [TestStatus.SUCCESS, TestStatus.WARNING]

        metric_value = str(round(payload["metrics"][0]["value"], 3))
        result = payload["tests"][0]["description"]
        status_bool = is_passed(payload["tests"][0]["status"])

        return self.get_test_case_result_object(
            execution_date = self.execution_date,
            status = self.get_test_case_status(status_bool),
            result = result,
            test_result_value = [TestResultValue(name="metric_value",
                                                 value=metric_value,
                                                 predictedValue=None),
                                 TestResultValue(name="description",
                                                 value=self._get_description(),
                                                 predictedValue=None),
            ],
        )

    def _housekeeping(self):
        ts = self.execution_date.root // 1000  # 執行時間
        time_zone = os.environ.get("REPORT_TIMEZONE", "UTC")
        dt = datetime.fromtimestamp(ts).astimezone(ZoneInfo(time_zone))
        with sqlite3.connect(str(self.report_dir / "report_catalog.db")) as conn:
            cursor = conn.cursor()
            # 寫入本次報告
            cursor.execute(
                """
                INSERT INTO report_catalog(test_case, file_name, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    self.test_case.name.root,
                    self.report_name,
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            # 讀取報告清單
            cursor.execute(
                f"""
                SELECT file_name, id
                FROM report_catalog
                WHERE test_case = '{self.test_case.name.root}' AND is_deleted = 0
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()
            # 刪除過早報告
            for file_name, file_id in rows[self.max_report:]:
                (self.report_dir / file_name / "").with_suffix(".html").unlink(missing_ok=True)
                cursor.execute(
                    f"""
                    UPDATE report_catalog
                    SET is_deleted = 1
                    WHERE id = {file_id}
                    """
                )
            conn.commit()

    def _get_description(self) -> str:
        if self.test_case.description:
            des = self.test_case.description.root
        else:
             des = ""

        sep = "<p><==========以下為程式自動產生，請勿修改==========></p>"
        des = des.split(sep)[0]
        with sqlite3.connect(str(self.report_dir / "report_catalog.db")) as conn:
            cursor = conn.cursor()
             # 讀取報告清單
            cursor.execute(
                f"""
                SELECT file_name, created_at
                FROM report_catalog
                WHERE test_case = '{self.test_case.name.root}' AND is_deleted = 0
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()
        rows = [f'<p><a target="_blank" rel="noopener noreferrer" href="/reports/{file_name}">報告連結-{created_at}</a></p>' for file_name, created_at in rows]
        rows.insert(1, "<p>===========================================</p>")
        des = des + sep + "".join(rows)

        return des

    def run_validation(self) -> TestCaseResult:
        self.runner = cast("QueryRunner", self.runner)
        target_column_name = get_decoded_column(self.test_case.entityLink.root)
        target_column = inspect(self.runner.table).c.get(target_column_name) # pyright: ignore[reportOptionalMemberAccess]

        date_column_name = self.get_test_case_param_value(
            self.test_case.parameterValues, # pyright: ignore[reportArgumentType]
            "DateColumn",
            str,
        )
        date_column_name = cast(str, date_column_name)
        # assert date_column_name is not None
        date_column = inspect(self.runner.table).c.get(date_column_name) # pyright: ignore[reportOptionalMemberAccess]
        if date_column is None:
            raise ValueError(f"columnn {date_column_name} doesn't exists!")

        baseline_value = self.get_test_case_param_value(
            self.test_case.parameterValues, # pyright: ignore[reportArgumentType]
            "BaselineValue",
            str,
            default = None
        )
        baseline_value = cast(Optional[str], baseline_value)

        dt_cur, dt_ref = self.get_cond_for_comparison(date_column,
                                                      baseline_value)
        # df_cur
        stmt = select(target_column).where(date_column == dt_cur)
        rows = self.runner.session.execute(stmt).all()
        df_cur = pd.DataFrame(rows)
        # df_ref
        stmt = select(target_column).where(date_column == dt_ref)
        rows = self.runner.session.execute(stmt).all()
        df_ref = pd.DataFrame(rows)
        # report
        report = Report(metrics=[ValueDrift(column=target_column_name)], include_tests=True)
        output = report.run(reference_data=df_ref, current_data=df_cur)

        output.save_html(str(self.report_dir / f"{self.report_name}.html"))

        self._housekeeping()
        return self._report_output_2_test_case_result(output)

    def get_cond_for_comparison(self,
                                date_column: "Column",
                                baseline_value: Optional[str] = None) -> tuple["SupportedColType", "SupportedColType"]:
        stmt = select(date_column).distinct().order_by(date_column.desc())
        dates = [x[0] for x in self.runner.session.execute(stmt).all()]
        if baseline_value is None:
            if len(dates) == 1:
                return dates[0], dates[0]
            return dates[0], dates[1]
        date_col_type = date_column.type.python_type.__name__ # pyright: ignore[reportAttributeAccessIssue] TODO
        match date_col_type:
            case "int":
                baseline_value = int(baseline_value) # pyright: ignore[reportAssignmentType]
            case "str":
                pass
            case "date":
                baseline_value = parser.parse(baseline_value).date() # pyright: ignore[reportAssignmentType]
            case "datetime":
                baseline_value = parser.parse(baseline_value) # pyright: ignore[reportAssignmentType]
            case _:
                raise RuntimeError("not supposed to be reached!")
        if baseline_value not in dates:
            raise ValueError(f"baseline_value {baseline_value} doesn't exists!")
        return dates[0], baseline_value # pyright: ignore[reportReturnType]
