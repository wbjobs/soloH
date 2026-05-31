import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.mock_data_generator import (
    generate_mock_transactions,
    generate_mock_suspicious_patterns,
    generate_mock_clusters,
    generate_mock_tasks,
    generate_mock_graph_data,
    generate_txid,
)


def create_sample_csv(output_path: str, tx_count: int = 15) -> None:
    print(f"Generating sample CSV with {tx_count} transactions...")

    data = generate_mock_transactions(address_count=20, tx_count=tx_count)

    csv_lines = [
        "txid,block_height,block_time,input_addresses,input_values,output_addresses,output_values,fee"
    ]

    for tx in data["transactions"]:
        tx_inputs = [inp for inp in data["tx_inputs"] if inp["txid"] == tx["txid"]]
        tx_outputs = [out for out in data["tx_outputs"] if out["txid"] == tx["txid"]]

        input_addresses = ";".join([inp["address"] for inp in tx_inputs])
        input_values = ";".join([str(inp["value"]) for inp in tx_inputs])
        output_addresses = ";".join([out["address"] for out in tx_outputs])
        output_values = ";".join([str(out["value"]) for out in tx_outputs])

        block_time_str = tx["block_time"].strftime("%Y-%m-%d %H:%M:%S")

        csv_lines.append(
            f"{tx['txid']},{tx['block_height']},{block_time_str},"
            f"{input_addresses},{input_values},{output_addresses},{output_values},{tx['fee']}"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(csv_lines))

    print(f"Sample CSV saved to: {output_path}")


async def insert_transaction_data(data: dict, clear_existing: bool = False) -> None:
    from app.models.blockchain import Block, Transaction, TxInput, TxOutput, Address, GraphEdge
    from app.core.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as session:
        if clear_existing:
            print("Clearing existing data...")
            await session.execute(text("TRUNCATE TABLE graph_edges CASCADE"))
            await session.execute(text("TRUNCATE TABLE tx_inputs CASCADE"))
            await session.execute(text("TRUNCATE TABLE tx_outputs CASCADE"))
            await session.execute(text("TRUNCATE TABLE transactions CASCADE"))
            await session.execute(text("TRUNCATE TABLE blocks CASCADE"))
            await session.execute(text("TRUNCATE TABLE addresses CASCADE"))
            await session.commit()

        print(f"Inserting {len(data['blocks'])} blocks...")
        blocks = [Block(**block) for block in data["blocks"]]
        session.add_all(blocks)
        await session.commit()

        print(f"Inserting {len(data['addresses'])} addresses...")
        addresses = [Address(**addr) for addr in data["addresses"]]
        session.add_all(addresses)
        await session.commit()

        print(f"Inserting {len(data['transactions'])} transactions...")
        transactions = [Transaction(**tx) for tx in data["transactions"]]
        session.add_all(transactions)
        await session.commit()

        print(f"Inserting {len(data['tx_inputs'])} transaction inputs...")
        tx_inputs = [TxInput(**inp) for inp in data["tx_inputs"]]
        session.add_all(tx_inputs)
        await session.commit()

        print(f"Inserting {len(data['tx_outputs'])} transaction outputs...")
        tx_outputs = [TxOutput(**out) for out in data["tx_outputs"]]
        session.add_all(tx_outputs)
        await session.commit()

        print("Generating graph edges...")
        graph_edges = []
        for tx in data["transactions"]:
            tx_inputs = [inp for inp in data["tx_inputs"] if inp["txid"] == tx["txid"]]
            tx_outputs = [out for out in data["tx_outputs"] if out["txid"] == tx["txid"]]

            for inp in tx_inputs:
                for out in tx_outputs:
                    if inp["address"] != out["address"]:
                        value = min(inp["value"], out["value"])
                        if value > 0:
                            graph_edges.append(
                                GraphEdge(
                                    from_address=inp["address"],
                                    to_address=out["address"],
                                    txid=tx["txid"],
                                    value=value,
                                    block_time=tx["block_time"],
                                )
                            )

        print(f"Inserting {len(graph_edges)} graph edges...")
        session.add_all(graph_edges)
        await session.commit()


async def insert_suspicious_patterns(clear_existing: bool = False) -> None:
    from app.models.analysis import SuspiciousPattern
    from app.core.database import async_session_factory
    from sqlalchemy import text
    patterns = generate_mock_suspicious_patterns()

    async with async_session_factory() as session:
        if clear_existing:
            await session.execute(text("TRUNCATE TABLE suspicious_patterns CASCADE"))
            await session.commit()

        print(f"Inserting {len(patterns)} suspicious patterns...")
        pattern_objs = [SuspiciousPattern(**p) for p in patterns]
        session.add_all(pattern_objs)
        await session.commit()


async def insert_clusters(clear_existing: bool = False) -> None:
    from app.models.analysis import AddressCluster, ClusterMember
    from app.core.database import async_session_factory
    from sqlalchemy import text
    data = generate_mock_clusters()

    async with async_session_factory() as session:
        if clear_existing:
            await session.execute(text("TRUNCATE TABLE cluster_members CASCADE"))
            await session.execute(text("TRUNCATE TABLE address_clusters CASCADE"))
            await session.commit()

        print(f"Inserting {len(data['clusters'])} address clusters...")
        clusters = [AddressCluster(**c) for c in data["clusters"]]
        session.add_all(clusters)
        await session.commit()

        print(f"Inserting {len(data['cluster_members'])} cluster members...")
        members = [ClusterMember(**m) for m in data["cluster_members"]]
        session.add_all(members)
        await session.commit()


async def insert_tasks(clear_existing: bool = False) -> None:
    from app.models.task import Task, TaskLog
    from app.core.database import async_session_factory
    from sqlalchemy import text
    data = generate_mock_tasks()

    async with async_session_factory() as session:
        if clear_existing:
            await session.execute(text("TRUNCATE TABLE task_logs CASCADE"))
            await session.execute(text("TRUNCATE TABLE tasks CASCADE"))
            await session.commit()

        print(f"Inserting {len(data['tasks'])} tasks...")
        tasks = [Task(**t) for t in data["tasks"]]
        session.add_all(tasks)
        await session.commit()

        print(f"Inserting {len(data['task_logs'])} task logs...")
        logs = [TaskLog(**l) for l in data["task_logs"]]
        session.add_all(logs)
        await session.commit()


async def generate_all(address_count: int, tx_count: int, clear_existing: bool = False) -> None:
    from app.core.database import init_db, close_db
    await init_db()

    try:
        print("=" * 60)
        print("Generating Mock Transaction Data")
        print("=" * 60)
        tx_data = generate_mock_transactions(address_count=address_count, tx_count=tx_count)
        await insert_transaction_data(tx_data, clear_existing=clear_existing)

        print("\n" + "=" * 60)
        print("Generating Suspicious Patterns")
        print("=" * 60)
        await insert_suspicious_patterns(clear_existing=clear_existing)

        print("\n" + "=" * 60)
        print("Generating Address Clusters")
        print("=" * 60)
        await insert_clusters(clear_existing=clear_existing)

        print("\n" + "=" * 60)
        print("Generating Tasks")
        print("=" * 60)
        await insert_tasks(clear_existing=clear_existing)

        print("\n" + "=" * 60)
        print("All mock data generated successfully!")
        print("=" * 60)
        print(f"Summary:")
        print(f"  - Blocks: {len(tx_data['blocks'])}")
        print(f"  - Addresses: {len(tx_data['addresses'])}")
        print(f"  - Transactions: {len(tx_data['transactions'])}")
        print(f"  - Transaction Inputs: {len(tx_data['tx_inputs'])}")
        print(f"  - Transaction Outputs: {len(tx_data['tx_outputs'])}")

    finally:
        await close_db()


async def main():
    parser = argparse.ArgumentParser(description="Generate mock Bitcoin transaction data")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    all_parser = subparsers.add_parser("all", help="Generate all mock data")
    all_parser.add_argument("--addresses", type=int, default=100, help="Number of addresses to generate")
    all_parser.add_argument("--transactions", type=int, default=500, help="Number of transactions to generate")
    all_parser.add_argument("--clear", action="store_true", help="Clear existing data before inserting")

    tx_parser = subparsers.add_parser("transactions", help="Generate transaction data only")
    tx_parser.add_argument("--addresses", type=int, default=100, help="Number of addresses to generate")
    tx_parser.add_argument("--transactions", type=int, default=500, help="Number of transactions to generate")
    tx_parser.add_argument("--clear", action="store_true", help="Clear existing data before inserting")

    subparsers.add_parser("patterns", help="Generate suspicious patterns only")
    subparsers.add_parser("clusters", help="Generate address clusters only")
    subparsers.add_parser("tasks", help="Generate tasks only")

    csv_parser = subparsers.add_parser("csv", help="Generate sample CSV file")
    csv_parser.add_argument("--output", type=str, default=str(project_root / "data" / "sample_transactions.csv"), help="Output CSV file path")
    csv_parser.add_argument("--count", type=int, default=15, help="Number of transactions in CSV")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "all":
        await generate_all(address_count=args.addresses, tx_count=args.transactions, clear_existing=args.clear)
    elif args.command in ["transactions", "patterns", "clusters", "tasks"]:
        from app.core.database import init_db, close_db
        await init_db()
        try:
            if args.command == "transactions":
                data = generate_mock_transactions(address_count=args.addresses, tx_count=args.transactions)
                await insert_transaction_data(data, clear_existing=args.clear)
            elif args.command == "patterns":
                await insert_suspicious_patterns()
            elif args.command == "clusters":
                await insert_clusters()
            elif args.command == "tasks":
                await insert_tasks()
        finally:
            await close_db()
    elif args.command == "csv":
        create_sample_csv(output_path=args.output, tx_count=args.count)


if __name__ == "__main__":
    asyncio.run(main())
