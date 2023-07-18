"""
demo_cdc_data
DAG auto-generated by Astro Cloud IDE.
"""

from airflow.decorators import dag
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from astro import sql as aql
import pandas as pd
import pendulum

# This is called before every cell run

from airflow import DAG
from airflow.providers.microsoft.azure.hooks import wasb
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pandas as pd
import requests

from datetime import datetime, timedelta
from io import BytesIO
import json
import logging

logger = logging.getLogger(__name__)

azure = wasb.WasbHook(wasb_conn_id='test_azure_connection')  # Also has async

pipeline_id = '3187bb07-94ea-4f9c-bacf-0b89506321bc'

# Functions must be defined here
def call_galactus(agent: str, payload: dict):
    # Import inside function for easy copy/paste to other demos
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }

    try:
        url = f'https://usafacts-data.azurewebsites.net/api/galactus/{agent}?code=TLXAxCb6DdIsjOS1P2ZakrS2bvAYQ3RkTurY0hQcBupnAzFu7lHHnQ=='
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        raise ValueError(e.args[0])

def get_most_recent_blob(container):
    # Should be handled by this but get does not exist https://airflow.apache.org/docs/apache-airflow-providers-microsoft-azure/stable/_api/airflow/providers/microsoft/azure/hooks/wasb/index.html#airflow.providers.microsoft.azure.hooks.wasb.WasbHook.get_blobs_list_recursive
    container_client = azure._get_container_client(container)
    blobs = [blob for blob in container_client.list_blobs() if pipeline_id in blob['name']]
    if len(blobs) == 0:
        raise Exception(f'No blobs found for pipeline {pipeline_id}. Are you sure it exists?')
    # Get most recent blob name
    return max(blobs, key=lambda x: x['last_modified'])


@aql.dataframe(task_id="wild_to_bronze")
def wild_to_bronze_func():
    agent = 'data_ingestion_agent_url'
    payload = {
        'pipelineId': pipeline_id,
        'createBy': 'eddyn@usafacts.org',
        'codeLocation': 'airflow',
        'url': 'https://www.cdc.gov/wcms/vizdata/poxvirus/monkeypox/data/USmap_counts.csv?2032-08-18T11:30:00.000Z',
    }
    response = call_galactus(agent, payload)
    return response.status_code

@aql.dataframe(task_id="bronze_to_json")
def bronze_to_json_func():
    # This would be equivalent to an agent/service that does "bronze to parquet", but Galactus used json
    agent = 'data_extraction_agent_csv'
    payload = {'pipelineId': pipeline_id, 'createBy': 'eddyn@usafacts.org', 'codeLocation': 'airflow'}
    response = call_galactus(agent, payload)
    return response.status_code

@dag(
    schedule="0 0 * * *",
    start_date=pendulum.from_format("2023-07-14", "YYYY-MM-DD").in_tz("UTC"),
    catchup=False,
)
def demo_cdc_data():
    wild_to_bronze = wild_to_bronze_func()

    bronze_to_json = bronze_to_json_func()

    databricks_json_to_dimensionalized = DatabricksRunNowOperator(
        job_name="Run_Databricks_From_Airflow",
        databricks_conn_id="test_databricks_connection",
        task_id="databricks_json_to_dimensionalized",
    )

    bronze_to_json << wild_to_bronze

    databricks_json_to_dimensionalized << bronze_to_json

dag_obj = demo_cdc_data()
