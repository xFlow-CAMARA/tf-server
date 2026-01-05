"""
SQLite storage implementation
"""

import json
import sqlite3
from functools import wraps
from typing import Dict, List, Optional, Union

from sunrise6g_opensdk.edgecloud.adapters.aeros import config
from sunrise6g_opensdk.edgecloud.adapters.aeros.storageManagement.appStorageManager import (
    AppStorageManager,
)
from sunrise6g_opensdk.edgecloud.core.camara_schemas import (
    AppId,
    AppInstanceId,
    AppInstanceInfo,
    AppInstanceName,
    AppProvider,
    EdgeCloudZoneId,
    Status,
)
from sunrise6g_opensdk.logger import setup_logger

decorator_logger = setup_logger()


def debug_log(msg: str):
    """
    Decorator that logs the given message if config.DEBUG is True.
    """

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            if config.DEBUG:
                decorator_logger.debug("[DEBUG] %s", msg)
            return func(*args, **kwargs)

        return wrapper

    return decorator


class SQLiteAppStorage(AppStorageManager):
    """
    SQLite storage implementation
    """

    @debug_log("Initializing SQLITE storage manager")
    def __init__(self, db_path: str = "app_storage.db"):
        if config.DEBUG:
            self.logger = setup_logger()
            self.logger.info("DB Path: %s", db_path)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        if config.DEBUG:
            self.logger.info("Initializing db schema")
        cursor = self.conn.cursor()
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS apps (
            app_id TEXT PRIMARY KEY,
            manifest TEXT
        );
        """
        )
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS deployments (
            app_instance_id TEXT PRIMARY KEY,
            app_id TEXT,
            name TEXT,
            app_provider TEXT,
            status TEXT,
            component_endpoint_info TEXT,
            kubernetes_cluster_ref TEXT,
            edge_cloud_zone_id TEXT
        );
        """
        )
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS stopped (
            app_id TEXT,
            app_instance_id TEXT
        );
        """
        )
        self.conn.commit()

    @debug_log("In SQLITE store_app method ")
    def store_app(self, app_id: str, manifest: Dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO apps (app_id, manifest) VALUES (?, ?);",
            (app_id, json.dumps(manifest)),
        )
        self.conn.commit()

    @debug_log("In SQLITE get_app method ")
    def get_app(self, app_id: str) -> Optional[Dict]:
        row = self.conn.execute("SELECT manifest FROM apps WHERE app_id = ?;", (app_id,)).fetchone()
        return json.loads(row[0]) if row else None

    @debug_log("In SQLITE app_exists method ")
    def app_exists(self, app_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM apps WHERE app_id = ?;", (app_id,)).fetchone()
        return row is not None

    @debug_log("In SQLITE list_apps method ")
    def list_apps(self) -> List[Dict]:
        rows = self.conn.execute("SELECT manifest FROM apps;").fetchall()
        return [json.loads(row[0]) for row in rows]

    @debug_log("In SQLITE delete_app method ")
    def delete_app(self, app_id: str) -> None:
        self.conn.execute("DELETE FROM apps WHERE app_id = ?;", (app_id,))
        self.conn.commit()

    @debug_log("In SQLITE store_deployment method ")
    def store_deployment(self, app_instance: AppInstanceInfo) -> None:
        resolved_status = (
            str(app_instance.status.value)
            if hasattr(app_instance.status, "value")
            else str(app_instance.status) if app_instance.status else "unknown"
        )
        self.logger.info("Resolved status for DB insert: %s", resolved_status)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO deployments (
                app_instance_id, app_id, name, app_provider, status,
                component_endpoint_info, kubernetes_cluster_ref, edge_cloud_zone_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(app_instance.appInstanceId),
                str(app_instance.appId),
                str(app_instance.name.root),
                str(app_instance.appProvider.root),
                (
                    str(app_instance.status.value)
                    if hasattr(app_instance.status, "value")
                    else str(app_instance.status) if app_instance.status else "unknown"
                ),
                (
                    json.dumps(app_instance.componentEndpointInfo)
                    if app_instance.componentEndpointInfo
                    else None
                ),
                app_instance.kubernetesClusterRef,
                str(app_instance.edgeCloudZoneId.root),
            ),
        )

        self.conn.commit()

    @debug_log("In SQLITE get_deployments method ")
    def get_deployments(self, app_id: Optional[str] = None) -> Dict[str, List[str]]:
        if app_id:
            rows = self.conn.execute(
                "SELECT app_id, app_instance_id FROM deployments WHERE app_id = ?;", (app_id,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT app_id, app_instance_id FROM deployments;").fetchall()

        result: Dict[str, List[str]] = {}
        for app_id_val, instance_id in rows:
            result.setdefault(app_id_val, []).append(instance_id)
        return result

    @debug_log("In SQLITE find_deployments method ")
    def find_deployments(
        self,
        app_id: Optional[str] = None,
        app_instance_id: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[AppInstanceInfo]:
        query = "SELECT * FROM deployments WHERE 1=1"
        params = []
        if app_id:
            query += " AND app_id = ?"
            params.append(app_id)
        if app_instance_id:
            query += " AND app_instance_id = ?"
            params.append(app_instance_id)

        rows = self.conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            result.append(
                AppInstanceInfo(
                    appInstanceId=AppInstanceId(row[0]),
                    appId=AppId(row[1]),
                    name=AppInstanceName(row[2]),
                    appProvider=AppProvider(row[3]),
                    status=Status(row[4]) if row[4] else Status.unknown,
                    componentEndpointInfo=json.loads(row[5]) if row[5] else None,
                    kubernetesClusterRef=row[6],
                    edgeCloudZoneId=EdgeCloudZoneId(row[7]),
                )
            )

        return result

    @debug_log("In SQLITE remove_deployments method ")
    def remove_deployment(self, app_instance_id: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT app_id FROM deployments WHERE app_instance_id = ?;", (app_instance_id,)
        ).fetchone()
        self.conn.execute("DELETE FROM deployments WHERE app_instance_id = ?;", (app_instance_id,))
        self.conn.commit()
        return row[0] if row else None

    @debug_log("In SQLITE store_stopped_instance method ")
    def store_stopped_instance(self, app_id: str, app_instance_id: str) -> None:
        self.conn.execute(
            "INSERT INTO stopped (app_id, app_instance_id) VALUES (?, ?);",
            (app_id, app_instance_id),
        )
        self.conn.commit()

    @debug_log("In SQLITE get_Stopped_instances method ")
    def get_stopped_instances(
        self, app_id: Optional[str] = None
    ) -> Union[List[str], Dict[str, List[str]]]:
        if app_id:
            rows = self.conn.execute(
                "SELECT app_instance_id FROM stopped WHERE app_id = ?;", (app_id,)
            ).fetchall()
            return [r[0] for r in rows]
        else:
            rows = self.conn.execute("SELECT app_id, app_instance_id FROM stopped;").fetchall()
            result: Dict[str, List[str]] = {}
            for aid, iid in rows:
                result.setdefault(aid, []).append(iid)
            return result

    @debug_log("In SQLITE remove_stopped_instances method ")
    def remove_stopped_instances(self, app_id: str) -> None:
        self.conn.execute("DELETE FROM stopped WHERE app_id = ?;", (app_id,))
        self.conn.commit()
