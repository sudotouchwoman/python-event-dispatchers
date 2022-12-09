## **Chart proposals:**
+ Waterfall chart for task status
+ \# of aborted tasks with extended info scraped from agent
+ \# of processed tasks per agent
+ Status chart for each component instance (per agent, per task producer etc)


Task messages are emitted by one of agent's components (dashboard) on logical task state changes and by task producer component.
Sample message format for tasks:

```json
{
    "id_task": 0,
    "datetime": "YYYY-MM-DD HH:MM:SS.mmm",
    "level": "info/warning/error",
    "status": "created/submitted/aborted/finished",
    "created_by": 0,
    "assigned_to": 777
}
```

Agent state can be monitored too via dedicated topic/table.
Sample message format for agent pings (state switches):

```json
{
    "level": "info",
    "id_agent": 777,
    "datetime": "YYYY-MM-DD HH:MM:SS.mm",
    "message": "waiting for next task",
    "state": "idle",
    "curent_loc": ""
}
```

When something goes wrong, agent might additionally send some meaningful additional info.
This can be helpful in narrowing down the incident reason.
Sample agent incident message format (when something goes wrong,
this one might be fired):

```json
{
    // general info
    "level": "error",
    "id_agent": 777,
    "datetime": "YYYY-MM-DD HH:MM:SS.mm",
    "message": "something went wrong (e.g. network problem)",
    // error-specific attributes
    "last_state": "await_path",
    "task": {
        "id_current_task": 42,
        "current_subtask": 1,
        "subtasks_left": 2,
    },
    "curent_loc": "location-code",
    "target_loc": "target-location-code",
    // more info can be attached on demand
    "pings": {
        "idle": 0,
        "recover": 0,
        "await_path": 5
    }
}
```

One point is, data might be duplicated with this schema.
Possibly we would like to submit to several topics a time (e.g. to both agent status topic and to incident topic too).

When dealing with systems with JSON support (MongoDB, Redis, Kafka), aggregation can be done easier

## **Sending time series data**

Python has clients for [influxDB](https://docs.influxdata.com/influxdb/cloud/api-guide/client-libraries/python/) and [Prometheus](https://pypi.org/project/prometheus-client/), which can also be used as datasources for Grafana. These clients can be easily integrated with logging routines and send logs/traces/metrics (whichever we implement). Time-series databases can be useful when it comes to data invalidation and can generally operate with several environments (buckets) or namespaces to separate data entries. Configuration is code-driven.

## **Store data in relational DB (PostgreSQL, MySQL)**

Grafana supports querying data from these databases too, but they can be too heavy for our problem and are less flexible in terms of data format (table schemas). However, JSON format can be easily translated to a table schema. Moreover, such DBs shine when it comes to aggregation (say, joining tables) and processing performance. We can store messages from different components of our system in different tables.

Possible SQL table schemas (**NOT** tested against real database, this is just some draft code, check for syntax errors first):

```sql
CREATE TABLE producers (
    id_producer INT PRIMARY KEY AUTOINCREMENT,
    -- additional producer data
);

CREATE TABLE tasks (
    id_task INT PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME NOT NULL,
    created_by INT NOT NULL,
    CONSTRAINT FK_id_producer FOREIGN KEY (created_by)
    REFERENCES producers(id_producer)
);

CREATE TABLE agents (
    id_agent INT PRIMARY KEY AUTOINCREMENT,
    controlled_by INT NOT NULL,
    CONSTRAINT FK_id_producer FOREIGN KEY (controlled_by)
    REFERENCES producers(id_producer)
);

CREATE TABLE lifts (
    id_agent INT PRIMARY KEY AUTOINCREMENT,
    -- additional component data
    -- actually, we might store all components ids in
    -- a single table like components
);

CREATE TABLE log_records (
    id_record INT PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME NOT NULL,
    created_by INT NOT NULL, -- foreign key for arbitrary component
    -- we can specify the component type in an additional column as
    -- this metadata is known at logging time like this:
    component_type VARCHAR(255) NOT NULL,
    log_level INT,
    msg TEXT NOT NULL,
);

CREATE TABLE agent_error_records (
    id_record INT PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME NOT NULL,
    created_by INT NOT NULL, -- foreign key to agent id
    severity INT, -- logging level or somewhat more meaningful
    reason TEXT NOT NULL,
    last_sane_state INT NOT NULL, -- state agent was in when error occured
    aborted_task_id INT, -- task agent was performing when error occured
    -- nullable since in general case, error might occur when agent is idle
    CONSTRAINT FK_id_agent FOREIGN KEY (created_by)
    REFERENCES agents(id_agent)
    CONSTRAINT FK_id_task FOREIGN KEY (aborted_task_id)
    REFERENCES tasks(id_task)
);
```
