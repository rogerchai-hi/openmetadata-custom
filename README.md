# OpenMetadata 客製化資料漂移擴充功能

本專案以 [OpenMetadata](https://open-metadata.org/) 為基礎，提供了一個客製化的資料品質測試，用於偵測特定資料表欄位的資料漂移 (Data Drift)。其利用 [Evidently](https://github.com/evidentlyai/evidently) 套件來比較不同時間點的資料分佈及產生視覺化報告，並直接整合到 OpenMetadata 的使用者介面中。

>⚠️ 由於套件相容性問題，本專案並非使用Evidently的官方版本，而是使用僅保留資料漂移功能的[分支版本](https://github.com/rogerchai-hi/evidently-datadrift)


## 主要功能

- **客製化資料漂移測試:** 實現了一個欄位層級的 test type `Column Data Drift`，可在 OpenMetadata UI 中直接設定相關測試案例。
- **動態基準比對:** 可將最新的資料分區與前一個分區或使用者指定的基準日期進行比較。
- **報告管理:** 可直接在對應測試案例中的描述找到近五次的漂移測試報告連結 (報告由 Evidently 產生)，並直接透過網頁開啟查看 (**目前僅支援透過網頁查看，尚不支援透過郵件中超連結查看**)。
- **容器化環境:** 整套系統透過 Docker 和 Docker Compose 進行管理，以簡化部署和依賴管理。

## 如何部署

1. **下載專案檔案:** 可直接 git clone 或是將本專案`./docker/`資料料夾搬移至目標目錄。
```bash
git clone https://github.com/rogerchai-hi/openmetadata-custom.git
```
2.  **啟動服務:** 啟動指令已寫在`./docker/Makefile`，可直接以 make 指令部署 (若前一步驟使用手動搬移資料夾，以下指令再自行更動工作路徑)。
```bash
cd openmetadata-custom/docker && make
```

## 專案架構
```text
.
├─docker               # Docker 相關配置檔案
│  ├─ingestion         # ingestion Docker 相關配置
│  ├─nginx             # nginx Docker 相關配置
│  └─openmetadata      # OpenMetadata docker compose yaml 檔
└─metadata             # OpenMetadata 的 Namespace Package，用於擴充資料漂移功能
```
>⚠️ 若參考 [OpenMetadata 官方文件](https://docs.open-metadata.org/latest/how-to-guides/data-quality-observability/quality/custom-tests)，會注意到當中說明須針對 `__init__.py` 進行修改，但 Python 已於 [PEP420](https://peps.python.org/pep-0420/) 更新使 Namespace Package 不再需要定義 `__init__.py`，若依照 OpenMetadata 官方之修改方式，當服務重啟後會出現錯誤。

## 系統架構

此系統以 OpenMetadata [官方提供](https://docs.open-metadata.org/latest/quick-start/local-docker-deployment)之 PostgreSQL 版本設定檔`docker-compose-postgres.yml` 為基底，並加上`docker-compose-postgres.datadrift.yml` 共同定義，其中關鍵服務組成包含：

-   `nginx`: Nginx 伺服器，對 `openmetadata-server` 進行反向代理，並同時提供靜態 HTML 資料漂移報告。它在 **port 81** 上取代取代原先的`openmetadata-server`作為直接面對使用者的服務。
-   `ingestion`: 基於原始版本的 `ingestion` 進行了客製化，新增了資料漂移測試的後端功能。
-   `define-test-case`: 一個輔助服務，可以在啟動時自動在 OpenMetadata 中定義所需的資料漂移測試。
-   **其餘 OpenMetadata 服務:** 包含 `postgresql`、`openmetadata-server`、`elasticsearch`、`execute-migrate-all` 等原生 OpenMetadata 服務。

## 關鍵檔案

### metadata 相關
-   `metadata/data_quality/validations/column/sqlalchemy/datadrift.py`: 資料漂移測試的核心邏輯，處理漂移計算、相關報告產生與維護。
-   `metadata/ingestion/sink/metadata_rest.py`: 對 OpenMetadata 的Python SDK 原始碼進行修改，調整該檔案的 `write_test_case_result_list` 與 `write_test_case_results` method，使其在將測試結果回傳回 OpenMetadata Server 時可同步修改測試案例的描述。
-   `pyproject.toml` & `setup.py`: 定義專案的依賴項 (本專案開發以 `Poetry` 進行環境及套件管理)。

### docker 相關
-   `docker/ingestion/tmp/datadrift_definition.json`: 資料漂移測試的定義檔 (Test Definition)。
-   `docker/ingestion/tmp/datadrift_definition.py`: 用於將資料漂移的定義檔透過 API 註冊至 OpenMetadata 系統。
-   `docker/ingestion/tmp/report_catalog.py`: 用於建立資料漂移 HTML 報告的 Housekeeping DB (SQLite)。
-   `docker/ingestion/wheels/constraints.txt`: 已存在於原始 `ingestion` 中的 Python 套件清單，用於避免套件衝突。
-   `docker/ingestion/wheels/evidently-0.7.15+datadrift.2-py3-none-any.whl`: [Evidently 分支版本](https://github.com/rogerchai-hi/evidently-datadrift)的 wheel 檔 。
-   `docker/ingestion/wheels/metadata-0.3.1-py3-none-any.whl`: 本專案 OpenMetadata Python SDK 的 namespace package 打包後的 wheel 檔。