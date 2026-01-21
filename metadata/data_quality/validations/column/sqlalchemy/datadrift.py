import time
from functools import cached_property
from typing import TYPE_CHECKING, Optional, TypeAlias, cast

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
    from datetime import date, datetime

    from evidently.core.report import Snapshot
    from metadata.profiler.processor.runner import QueryRunner
    from sqlalchemy import Column
    SupportedColType: TypeAlias = int | str | date | datetime

class DatadriftValidator(BaseTestValidator):

    @cached_property
    def report_name(self):
        ts = int(time.time())
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

    def _get_description(self) -> str:
        if self.test_case.description:
            des = self.test_case.description.root
        else:
             des = ""
        return f'<p><a target="_blank" rel="noopener noreferrer" href="/reports/{self.report_name}">報告連結</a></p>{des}'
        # return f'<p><a target="_blank" rel="noopener noreferrer" href="http://localhost:81/reports/{self.report_name}">報告連結</a></p>{des}'
        #return f"/reports/{self.report_name}"

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

        output.save_html(f"/tmp/datadrift_report/{self.report_name}.html")

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
