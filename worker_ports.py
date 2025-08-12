from sqlalchemy import select, func
from models import WorkerBot

AVAILABLE_PORTS = [
    8001, 8002, 8003, 8004, 8005, 8006, 8007,
    8008, 8009, 8010, 8011, 8012, 8013, 8014, 8015,
    8016, 8017, 8018, 8019, 8020, 8021, 8022
]

async def get_least_loaded_port(session):
    port_counts = await session.execute(
        select(WorkerBot.server_port, func.count(WorkerBot.id))
        .group_by(WorkerBot.server_port)
    )
    port_counts_dict = {port: count for port, count in port_counts if port}
    min_count = min(port_counts_dict.values()) if port_counts_dict else 0
    for port in AVAILABLE_PORTS:
        if port_counts_dict.get(port, 0) <= min_count:
            return port
    return AVAILABLE_PORTS[0]