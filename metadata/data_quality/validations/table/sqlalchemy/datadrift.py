from typing import TYPE_CHECKING, cast

import pandas as pd
from evidently import Report
from evidently.legacy.tests.base_test import TestStatus
from evidently.metrics import ValueDrift
from metadata.data_quality.validations.base_test_handler import \
    BaseTestValidator
from metadata.generated.schema.tests.basic import (TestCaseResult,
                                                   TestResultValue)
from metadata.utils.entity_link import get_decoded_column
from sqlalchemy import inspect

if TYPE_CHECKING:
    from evidently.core.report import Snapshot
    from metadata.profiler.processor.runner import QueryRunner


class ColumnDataDriftValidator(BaseTestValidator):

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
                                                 predictedValue=None)],
        )

    def run_validation(self) -> TestCaseResult:
        self.runner = cast("QueryRunner", self.runner)
        target_column_name = get_decoded_column(self.test_case.entityLink.root)

        date_column_name = self.get_test_case_param_value(
            self.test_case.parameterValues, # pyright: ignore[reportArgumentType]
            "DateColumn",
            str,
        )
        # TODO: validation
        columns_name = [target_column_name, date_column_name]
        columns = [x for x in inspect(self.runner.table).c if x.name in columns_name] # pyright: ignore[reportOptionalMemberAccess]

        rows = self.runner.select_all_from_table(*columns)
        df = pd.DataFrame(rows, columns=[col.name for col in columns])
        df = df.reindex(columns = columns_name)

        dates = df[date_column_name].drop_duplicates().sort_values(ascending=False)
        if len(dates) < 2:
            raise ValueError("there should be at least two data dates to calculate data drift.")

        df_cur = df[df[date_column_name] == dates.iloc[1]]
        df_ref = df[df[date_column_name] == dates.iloc[0]]

        report = Report(metrics=[ValueDrift(column=target_column_name)], include_tests=True)
        output = report.run(reference_data=df_ref, current_data=df_cur)

        return self._report_output_2_test_case_result(output)



