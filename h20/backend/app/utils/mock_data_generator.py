import random
import string
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional

BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
BECH32_ALPHABET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'


def base58_encode(data: bytes) -> str:
    result = []
    value = int.from_bytes(data, 'big')
    while value > 0:
        value, remainder = divmod(value, 58)
        result.append(BASE58_ALPHABET[remainder])
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return '1' * pad + ''.join(reversed(result))


def bech32_polymod(values: List[int]) -> int:
    generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def bech32_encode(hrp: str, data: List[int]) -> str:
    values = data + [0, 0, 0, 0, 0, 0]
    polymod = bech32_polymod([ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp] + values) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + '1' + ''.join([BECH32_ALPHABET[d] for d in values[:-6] + checksum])


def generate_legacy_address() -> str:
    prefix = b'\x00'
    key_bytes = bytes([random.randint(0, 255) for _ in range(20)])
    data = prefix + key_bytes
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return base58_encode(data + checksum)


def generate_segwit_address() -> str:
    prefix = b'\x05'
    key_bytes = bytes([random.randint(0, 255) for _ in range(20)])
    data = prefix + key_bytes
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return base58_encode(data + checksum)


def generate_bech32_address() -> str:
    hrp = 'bc'
    version = 0
    key_bytes = bytes([random.randint(0, 255) for _ in range(32)])
    data = [version] + list(key_bytes)
    converted = []
    bits = 0
    value = 0
    for byte in data:
        value = (value << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            converted.append((value >> bits) & 0x1f)
    if bits > 0:
        converted.append((value << (5 - bits)) & 0x1f)
    return bech32_encode(hrp, converted)


def generate_txid() -> str:
    return hashlib.sha256(bytes([random.randint(0, 255) for _ in range(64)])).hexdigest()


def generate_mock_addresses(count: int) -> List[Dict[str, Any]]:
    addresses = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        rand = random.random()
        if rand < 0.6:
            address = generate_legacy_address()
        elif rand < 0.85:
            address = generate_segwit_address()
        else:
            address = generate_bech32_address()

        days_ago = random.randint(1, 365 * 3)
        first_seen = now - timedelta(days=days_ago)
        last_seen = first_seen + timedelta(days=random.randint(0, days_ago))

        total_received = round(random.uniform(0.001, 100), 8)
        total_sent = round(total_received * random.uniform(0.1, 0.95), 8)
        balance = round(total_received - total_sent, 8)
        tx_count = random.randint(1, 100)

        suspicious_score = None
        risk_level = None
        risk_factors = None

        if random.random() < 0.15:
            suspicious_score = round(random.uniform(0.5, 1.0), 2)
            if suspicious_score >= 0.8:
                risk_level = 'high'
            elif suspicious_score >= 0.6:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            risk_factors = {
                'unusual_activity': random.choice([True, False]),
                'mixing_service_association': random.choice([True, False]),
                'high_transaction_volume': random.choice([True, False]),
                'structuring_pattern': random.choice([True, False])
            }

        addresses.append({
            'address': address,
            'first_seen': first_seen,
            'last_seen': last_seen,
            'total_received': total_received,
            'total_sent': total_sent,
            'balance': balance,
            'tx_count': tx_count,
            'suspicious_score': suspicious_score,
            'risk_factors': risk_factors,
            'risk_level': risk_level
        })

    return addresses


def generate_mock_transactions(address_count: int, tx_count: int) -> Dict[str, Any]:
    addresses = generate_mock_addresses(address_count)
    address_list = [a['address'] for a in addresses]

    blocks = []
    transactions = []
    tx_inputs = []
    tx_outputs = []

    current_block_height = 800000
    now = datetime.now(timezone.utc)
    block_time = now - timedelta(days=30)

    spent_outputs = {}
    change_address_map = {}

    for i in range(tx_count):
        if i % random.randint(50, 150) == 0 or not blocks:
            block_height = current_block_height
            block_hash = hashlib.sha256(bytes([random.randint(0, 255) for _ in range(32)])).hexdigest()
            block_time = block_time + timedelta(minutes=random.randint(5, 15))
            blocks.append({
                'block_height': block_height,
                'block_hash': block_hash,
                'block_time': block_time,
                'tx_count': 0,
                'total_btc': 0
            })
            current_block_height += 1

        current_block = blocks[-1]
        txid = generate_txid()

        is_coinbase = random.random() < 0.05
        input_count = 1 if is_coinbase else random.randint(1, 5)
        output_count = random.randint(1, 4)

        inputs = []
        outputs = []
        total_input = 0
        total_output = 0

        if is_coinbase:
            reward = round(6.25 * random.uniform(0.95, 1.05), 8)
            inputs.append({
                'txid': txid,
                'vout': 0,
                'prev_txid': None,
                'prev_vout': None,
                'address': random.choice(address_list),
                'value': reward
            })
            total_input = reward

            for j in range(output_count):
                addr = random.choice(address_list)
                if j == 0:
                    val = round(reward * random.uniform(0.8, 1.0), 8)
                else:
                    val = round(reward * random.uniform(0.01, 0.2), 8)
                val = round(min(val, total_input - total_output - 0.0001), 8)
                if val <= 0:
                    break
                outputs.append({
                    'txid': txid,
                    'vout': j,
                    'address': addr,
                    'value': val,
                    'script_type': random.choice(['p2pkh', 'p2sh', 'p2wpkh', 'p2wsh']),
                    'is_spent': False
                })
                total_output = round(total_output + val, 8)
                spent_outputs[f'{txid}:{j}'] = False
        else:
            available_inputs = []
            for key, is_spent in spent_outputs.items():
                if not is_spent:
                    available_inputs.append(key)

            if len(available_inputs) < input_count:
                for j in range(input_count):
                    addr = random.choice(address_list)
                    val = round(random.uniform(0.0001, 10), 8)
                    prev_txid = generate_txid()
                    inputs.append({
                        'txid': txid,
                        'vout': j,
                        'prev_txid': prev_txid,
                        'prev_vout': random.randint(0, 3),
                        'address': addr,
                        'value': val
                    })
                    total_input = round(total_input + val, 8)
            else:
                selected_inputs = random.sample(available_inputs, input_count)
                for j, prev_key in enumerate(selected_inputs):
                    prev_txid, prev_vout = prev_key.split(':')
                    prev_vout = int(prev_vout)

                    prev_output = None
                    for out in tx_outputs:
                        if out['txid'] == prev_txid and out['vout'] == prev_vout:
                            prev_output = out
                            break

                    if prev_output:
                        addr = prev_output['address']
                        val = prev_output['value']
                        prev_output['is_spent'] = True
                        spent_outputs[prev_key] = True

                    inputs.append({
                        'txid': txid,
                        'vout': j,
                        'prev_txid': prev_txid,
                        'prev_vout': prev_vout,
                        'address': addr,
                        'value': val
                    })
                    total_input = round(total_input + val, 8)

            fee = round(total_input * random.uniform(0.0001, 0.001), 8)
            fee = max(fee, 0.00001)

            if len(inputs) == 1:
                change_addr = generate_bech32_address() if random.random() < 0.7 else generate_segwit_address()
                if inputs[0]['address'] not in change_address_map:
                    change_address_map[inputs[0]['address']] = []
                change_address_map[inputs[0]['address']].append(change_addr)
                address_list.append(change_addr)
                addresses.append({
                    'address': change_addr,
                    'first_seen': current_block['block_time'],
                    'last_seen': current_block['block_time'],
                    'total_received': 0,
                    'total_sent': 0,
                    'balance': 0,
                    'tx_count': 0,
                    'suspicious_score': None,
                    'risk_factors': None,
                    'risk_level': None
                })

            output_addrs = []
            for j in range(output_count):
                if j == output_count - 1 and len(inputs) == 1 and not output_addrs:
                    addr = change_address_map.get(inputs[0]['address'], [random.choice(address_list)])[-1]
                else:
                    addr = random.choice(address_list)
                    while addr in output_addrs:
                        addr = random.choice(address_list)
                output_addrs.append(addr)

                if j == output_count - 1:
                    val = round(total_input - total_output - fee, 8)
                else:
                    val = round((total_input - fee) * random.uniform(0.1, 0.9), 8)
                    val = min(val, total_input - total_output - fee - 0.00001)

                if val <= 0:
                    break

                outputs.append({
                    'txid': txid,
                    'vout': j,
                    'address': addr,
                    'value': val,
                    'script_type': random.choice(['p2pkh', 'p2sh', 'p2wpkh', 'p2wsh']),
                    'is_spent': False
                })
                total_output = round(total_output + val, 8)
                spent_outputs[f'{txid}:{j}'] = False

        fee = round(total_input - total_output, 8)
        if fee < 0:
            fee = 0.00001
            total_output = round(total_input - fee, 8)
            if outputs:
                outputs[-1]['value'] = round(total_output - sum(o['value'] for o in outputs[:-1]), 8)

        transactions.append({
            'txid': txid,
            'block_height': current_block['block_height'],
            'block_time': current_block['block_time'],
            'total_input': total_input,
            'total_output': total_output,
            'fee': fee,
            'input_count': len(inputs),
            'output_count': len(outputs),
            'is_coinbase': is_coinbase
        })

        tx_inputs.extend(inputs)
        tx_outputs.extend(outputs)

        current_block['tx_count'] += 1
        current_block['total_btc'] = round(current_block['total_btc'] + total_output, 8)

        for inp in inputs:
            for addr in addresses:
                if addr['address'] == inp['address']:
                    addr['total_sent'] = round(addr['total_sent'] + inp['value'], 8)
                    addr['balance'] = round(addr['total_received'] - addr['total_sent'], 8)
                    addr['tx_count'] += 1
                    addr['last_seen'] = max(addr['last_seen'], current_block['block_time'])

        for out in outputs:
            for addr in addresses:
                if addr['address'] == out['address']:
                    addr['total_received'] = round(addr['total_received'] + out['value'], 8)
                    addr['balance'] = round(addr['total_received'] - addr['total_sent'], 8)
                    addr['tx_count'] += 1
                    addr['last_seen'] = max(addr['last_seen'], current_block['block_time'])
                    if addr['first_seen'] is None or current_block['block_time'] < addr['first_seen']:
                        addr['first_seen'] = current_block['block_time']

    return {
        'addresses': addresses,
        'blocks': blocks,
        'transactions': transactions,
        'tx_inputs': tx_inputs,
        'tx_outputs': tx_outputs
    }


def generate_mock_graph_data(node_count: int, edge_count: int) -> Dict[str, Any]:
    addresses = generate_mock_addresses(node_count)
    address_list = [a['address'] for a in addresses]

    edges = []
    now = datetime.now(timezone.utc)

    for i in range(edge_count):
        from_addr = random.choice(address_list)
        to_addr = random.choice([a for a in address_list if a != from_addr])
        txid = generate_txid()
        value = round(random.uniform(0.0001, 10), 8)
        block_time = now - timedelta(days=random.randint(0, 30))

        edges.append({
            'from_address': from_addr,
            'to_address': to_addr,
            'txid': txid,
            'value': value,
            'block_time': block_time
        })

    return {
        'nodes': addresses,
        'edges': edges
    }


def generate_mock_suspicious_patterns() -> List[Dict[str, Any]]:
    addresses = generate_mock_addresses(20)
    address_list = [a['address'] for a in addresses]

    patterns = []
    now = datetime.now(timezone.utc)

    pattern_types = [
        ('layered_transfer', 'high', '分层转账模式，资金通过多个中间地址转移'),
        ('cyclic_transaction', 'high', '循环交易模式，资金在多个地址间循环流动'),
        ('structuring_split', 'medium', '结构化拆分，大额资金拆分为多笔小额交易'),
        ('sudden_large_transfer', 'medium', '异常大额转账'),
        ('mixing_pattern', 'high', '混币服务模式特征'),
        ('peeling_chain', 'medium', '逐层剥离式转账链'),
        ('dust_attack', 'low', '粉尘攻击特征'),
        ('coordinated_withdrawal', 'high', '协同取款模式')
    ]

    for i, (pattern_type, severity, description) in enumerate(pattern_types):
        pattern_address = random.choice(address_list)
        txid = generate_txid()
        confidence = round(random.uniform(0.7, 1.0), 4)

        evidence = []
        if pattern_type == 'layered_transfer':
            hop_addresses = random.sample([a for a in address_list if a != pattern_address], 4)
            evidence = [
                {'type': 'transfer_chain', 'addresses': [pattern_address] + hop_addresses, 'hops': 5},
                {'type': 'time_correlation', 'window_minutes': 60, 'count': 5}
            ]
        elif pattern_type == 'cyclic_transaction':
            cycle_addrs = random.sample([a for a in address_list if a != pattern_address], 3)
            evidence = [
                {'type': 'cycle_addresses', 'addresses': [pattern_address] + cycle_addrs + [pattern_address]},
                {'type': 'total_value', 'btc': round(random.uniform(1, 10), 4)}
            ]
        elif pattern_type == 'structuring_split':
            evidence = [
                {'type': 'split_count', 'count': random.randint(5, 20)},
                {'type': 'amount_range', 'min': 0.001, 'max': 0.01},
                {'type': 'original_amount', 'btc': round(random.uniform(0.5, 5), 4)}
            ]

        patterns.append({
            'pattern_type': pattern_type,
            'confidence': confidence,
            'severity': severity,
            'description': description,
            'evidence': evidence,
            'address': pattern_address,
            'txid': txid,
            'detected_at': now - timedelta(hours=random.randint(1, 720))
        })

    return patterns


def generate_mock_clusters() -> List[Dict[str, Any]]:
    addresses = generate_mock_addresses(50)
    address_list = [a['address'] for a in addresses]

    clusters = []
    cluster_members = []
    now = datetime.now(timezone.utc)

    heuristics = ['common_input_heuristic', 'change_address_heuristic', 'multi_input_heuristic']

    for i in range(8):
        cluster_id = str(uuid.uuid4())
        heuristic = random.choice(heuristics)
        confidence = round(random.uniform(0.7, 0.99), 4)
        size = random.randint(2, 8)
        cluster_addresses = random.sample(address_list, size)

        total_value = round(random.uniform(1, 100), 8)

        clusters.append({
            'cluster_id': cluster_id,
            'heuristic': heuristic,
            'confidence': confidence,
            'size': size,
            'total_value': total_value
        })

        for addr in cluster_addresses:
            cluster_members.append({
                'cluster_id': cluster_id,
                'address': addr,
                'joined_at': now - timedelta(days=random.randint(0, 30))
            })

            for address_obj in addresses:
                if address_obj['address'] == addr:
                    address_obj['cluster_id'] = cluster_id

    return {
        'clusters': clusters,
        'cluster_members': cluster_members,
        'addresses': addresses
    }


def generate_mock_tasks() -> List[Dict[str, Any]]:
    task_types = [
        'address_import',
        'transaction_import',
        'cluster_analysis',
        'pattern_detection',
        'graph_analysis',
        'risk_assessment',
        'csv_import',
        'block_sync'
    ]

    statuses = ['pending', 'running', 'completed', 'failed']

    tasks = []
    task_logs = []
    now = datetime.now(timezone.utc)

    for i in range(12):
        task_id = str(uuid.uuid4())
        task_type = random.choice(task_types)
        status = random.choice(statuses)
        progress = 0.0
        started_at = None
        completed_at = None
        result = None
        error_message = None

        created_at = now - timedelta(hours=random.randint(1, 72))

        if status in ['running', 'completed', 'failed']:
            started_at = created_at + timedelta(minutes=random.randint(1, 30))
            if status == 'completed':
                progress = 100.0
                completed_at = started_at + timedelta(minutes=random.randint(5, 120))
                result = {
                    'processed_count': random.randint(100, 10000),
                    'success_count': random.randint(100, 10000),
                    'total_value': round(random.uniform(10, 1000), 8)
                }
            elif status == 'running':
                progress = round(random.uniform(10, 90), 2)
            elif status == 'failed':
                progress = round(random.uniform(10, 70), 2)
                completed_at = started_at + timedelta(minutes=random.randint(5, 60))
                error_messages = [
                    'Database connection timeout',
                    'Invalid transaction format',
                    'Insufficient permissions',
                    'Network error when fetching data',
                    'Out of memory during processing'
                ]
                error_message = random.choice(error_messages)

        params = {
            'start_block': random.randint(700000, 800000),
            'end_block': random.randint(800000, 900000),
            'address_count': random.randint(100, 5000)
        }

        tasks.append({
            'task_id': task_id,
            'task_type': task_type,
            'status': status,
            'progress': progress,
            'error_message': error_message,
            'result': result,
            'params': params,
            'created_at': created_at,
            'started_at': started_at,
            'completed_at': completed_at
        })

        log_levels = ['INFO', 'DEBUG', 'WARNING', 'ERROR']
        log_count = random.randint(3, 10)
        log_time = created_at
        for j in range(log_count):
            log_time = log_time + timedelta(minutes=random.randint(1, 10))
            log_level = random.choice(log_levels)
            if status == 'failed' and j == log_count - 1:
                log_level = 'ERROR'

            log_messages = {
                'INFO': [
                    f'Task started: {task_type}',
                    f'Processing batch {j}/{log_count}',
                    f'Successfully processed {random.randint(10, 1000)} records',
                    'Connection established successfully',
                    'Data validation passed'
                ],
                'DEBUG': [
                    f'Fetching data for block range',
                    f'Processing address: {random.choice(generate_mock_addresses(1)[0]["address"])}',
                    f'Cache hit ratio: {round(random.uniform(0.5, 0.95), 2)}',
                    f'Memory usage: {random.randint(100, 1000)}MB'
                ],
                'WARNING': [
                    'Slow database query detected',
                    'High memory usage warning',
                    'Some data may be incomplete',
                    'Rate limit approaching'
                ],
                'ERROR': [
                    error_message or 'Unknown error occurred',
                    'Failed to process transaction',
                    'Connection lost, retrying...'
                ]
            }

            task_logs.append({
                'task_id': task_id,
                'log_level': log_level,
                'message': random.choice(log_messages[log_level]),
                'created_at': log_time
            })

    return {
        'tasks': tasks,
        'task_logs': task_logs
    }
