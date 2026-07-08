#!/usr/bin/env python3
"""
带实时监控和错误分析的迁移引擎全量测试脚本
"""

import requests
import json
import time
import os
from datetime import datetime
import threading
import sys
from collections import defaultdict
import statistics

# 全局监控数据
monitoring_data = {
    'start_time': datetime.now(),
    'total_cases': 0,
    'completed_cases': 0,
    'failed_cases': [],
    'error_count': 0,
    'response_times': [],
    'progress_history': [],
    'error_types': defaultdict(int),
    'slow_cases': []  # 超过60秒的用例
}

# 监控分析函数
def analyze_monitoring():
    """分析监控数据并输出报告"""
    while True:
        time.sleep(30)  # 每30秒分析一次

        if monitoring_data['completed_cases'] == 0:
            continue

        current_time = datetime.now()
        elapsed = (current_time - monitoring_data['start_time']).total_seconds()
        progress = monitoring_data['completed_cases'] / monitoring_data['total_cases'] * 100 if monitoring_data['total_cases'] > 0 else 0

        # 计算平均响应时间
        avg_response_time = statistics.mean(monitoring_data['response_times']) if monitoring_data['response_times'] else 0

        # 输出实时状态
        print(f"\n[监控分析 {current_time.strftime('%H:%M:%S')}]")
        print(f"  进度: {monitoring_data['completed_cases']}/{monitoring_data['total_cases']} ({progress:.1f}%)")
        print(f"  平均响应时间: {avg_response_time:.2f}s | 最慢: {max(monitoring_data['response_times']) if monitoring_data['response_times'] else 0}s")
        print(f"  失败案例: {len(monitoring_data['failed_cases'])} | API错误: {monitoring_data['error_count']}")

        # 检查异常
        if monitoring_data['error_count'] > 0 and monitoring_data['error_count'] / monitoring_data['completed_cases'] > 0.1:
            print(f"  ⚠️  错误率过高: {monitoring_data['error_count']}/{monitoring_data['completed_cases']} > 10%")

        if avg_response_time > 30:
            print(f"  ⚠️  响应时间过慢: 平均 {avg_response_time:.2f}s")

        # 显示最近的错误类型
        if monitoring_data['error_types']:
            print(f"  错误类型: {dict(list(monitoring_data['error_types'].items())[:3])}")

        # 如果进度停滞
        if len(monitoring_data['progress_history']) >= 3:
            recent_progress = [p['progress'] for p in monitoring_data['progress_history'][-3:]]
            if len(set(recent_progress)) == 1:  # 进度3次都相同
                print("  ⚠️  进度停滞，可能存在连接问题")

# 错误重试机制
def test_with_retry(case, max_retries=3):
    """带重试的测试"""
    for attempt in range(max_retries):
        try:
            start_time = time.time()

            if case['mode'] == 'fast':
                resp = requests.post('http://localhost:8080/migrate',
                    json={'source_sql': case['source_sql'], 'pair': case['pair'],
                          'retrieval': 'fast', 'fast': True},
                    timeout=120)
            else:
                resp = requests.post('http://localhost:8080/migrate',
                    json={'source_sql': case['source_sql'], 'pair': case['pair'],
                          'retrieval': 'full', 'fast': False},
                    timeout=120)

            response_time = time.time() - start_time
            monitoring_data['response_times'].append(response_time)

            if response_time > 60:
                monitoring_data['slow_cases'].append({
                    'id': case['id'],
                    'response_time': response_time,
                    'mode': case['mode']
                })

            result = resp.json()
            return {
                'success': True,
                'target_sql': result.get('target_sql', ''),
                'response_time': response_time
            }

        except Exception as e:
            error_msg = str(e)
            monitoring_data['error_count'] += 1
            monitoring_data['error_types'][type(e).__name__] += 1

            if attempt < max_retries - 1:
                print(f"    重试 {attempt + 1}/{max_retries} - 错误: {error_msg}")
                time.sleep(5)  # 等待5秒后重试
            else:
                return {
                    'success': False,
                    'error': error_msg,
                    'response_time': None
                }

# 主测试函数
def run_full_test():
    datasets = ['mysql_opengauss', 'mysql_postgres', 'oracle_pg', 'sqlserver_opengauss', 'sqlserver_postgres']

    # 统计总用例数
    total_cases = 0
    for ds in datasets:
        with open(f'eval/datasets/{ds}.jsonl', encoding='utf-8-sig') as f:
            total_cases += sum(1 for line in f if line.strip())

    monitoring_data['total_cases'] = total_cases

    print("="*80)
    print(f"开始全量测试 - 总用例: {total_cases}")
    print("="*80)

    # 启动监控线程
    monitor_thread = threading.Thread(target=analyze_monitoring)
    monitor_thread.daemon = True
    monitor_thread.start()

    results = {}

    for ds in datasets:
        print(f"\n\n=== 测试数据集: {ds} ===")
        ds_results = []

        with open(f'eval/datasets/{ds}.jsonl', encoding='utf-8-sig') as f:
            for line in f:
                if not line.strip():
                    continue

                case = json.loads(line)
                case_id = case['id']
                pair = case['pair']
                source_sql = case['source_sql']

                print(f"\n  [{case_id}] 测试中...", end='')

                # 测试 fast 模式
                fast_result = test_with_retry({
                    'id': case_id,
                    'source_sql': source_sql,
                    'pair': pair,
                    'mode': 'fast'
                })

                # 测试 full 模式
                full_result = test_with_retry({
                    'id': case_id,
                    'source_sql': source_sql,
                    'pair': pair,
                    'mode': 'full'
                })

                # 记录结果
                case_result = {
                    'id': case_id,
                    'pair': pair,
                    'fast_ok': fast_result['success'] and fast_result['target_sql'] == case.get('gold_target_sql', ''),
                    'full_ok': full_result['success'] and full_result['target_sql'] == case.get('gold_target_sql', ''),
                    'fast_pred': fast_result['target_sql'][:200] if fast_result['success'] else f"ERROR: {fast_result['error']}",
                    'full_pred': full_result['target_sql'][:200] if full_result['success'] else f"ERROR: {full_result['error']}",
                    'fast_time': fast_result['response_time'],
                    'full_time': full_result['response_time']
                }

                ds_results.append(case_result)

                # 更新进度
                monitoring_data['completed_cases'] += 1
                monitoring_data['progress_history'].append({
                    'time': (datetime.now() - monitoring_data['start_time']).total_seconds(),
                    'progress': monitoring_data['completed_cases'] / monitoring_data['total_cases'] * 100,
                    'failed_count': len(monitoring_data['failed_cases'])
                })

                # 记录失败案例
                if not case_result['fast_ok'] or not case_result['full_ok']:
                    monitoring_data['failed_cases'].append({
                        'id': case_id,
                        'dataset': ds,
                        'fast_ok': case_result['fast_ok'],
                        'full_ok': case_result['full_ok'],
                        'fast_time': case_result['fast_time'],
                        'full_time': case_result['full_time']
                    })

                time.sleep(1.5)  # 控制请求频率

        # 统计结果
        total = len(ds_results)
        fast_ok = sum(1 for r in ds_results if r['fast_ok'])
        full_ok = sum(1 for r in ds_results if r['full_ok'])

        # 计算平均响应时间
        fast_times = [r['fast_time'] for r in ds_results if r['fast_time']]
        full_times = [r['full_time'] for r in ds_results if r['full_time']]

        print(f"\n  {ds} 结果: {total} cases")
        print(f"  Fast mode: {fast_ok}/{total} ({fast_ok/total*100:.1f}%) | 平均耗时: {statistics.mean(fast_times):.2f}s" if fast_times else "")
        print(f"  Full mode: {full_ok}/{total} ({full_ok/total*100:.1f}%) | 平均耗时: {statistics.mean(full_times):.2f}s" if full_times else "")

        results[ds] = {
            'total': total,
            'fast_ok': fast_ok,
            'full_ok': full_ok,
            'fast_avg_time': statistics.mean(fast_times) if fast_times else 0,
            'full_avg_time': statistics.mean(full_times) if full_times else 0,
            'details': ds_results
        }

    # 生成完整报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_results(results, timestamp)

    print("\n" + "="*80)
    print("测试完成！")
    print(f"详细报告: eval/results/full_test_report_{timestamp}.md")
    print(f"原始数据: eval/results/full_test_data_{timestamp}.json")
    print("="*80)

def save_results(results, timestamp):
    """保存测试结果"""
    # 保存JSON数据
    with open(f'eval/results/full_test_data_{timestamp}.json', 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'monitoring': monitoring_data,
            'results': results
        }, f, ensure_ascii=False, indent=2)

    # 生成Markdown报告
    with open(f'eval/results/full_test_report_{timestamp}.md', 'w', encoding='utf-8') as f:
        f.write("# 迁移引擎全量测试报告（带监控分析）\n\n")
        f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**总用时**: {(datetime.now() - monitoring_data['start_time']).total_seconds():.0f} 秒\n\n")

        # 总体统计
        total_cases = sum(r['total'] for r in results.values())
        total_fast_ok = sum(r['fast_ok'] for r in results.values())
        total_full_ok = sum(r['full_ok'] for r in results.values())

        f.write("## 📊 总体结果\n\n")
        f.write(f"| 数据集 | 总数 | Fast 通过率 | Full 通过率 | Fast平均耗时 | Full平均耗时 |\n")
        f.write("|--------|------|------------|------------|--------------|--------------|\n")

        for ds, result in results.items():
            fast_rate = result['fast_ok']/result['total']*100 if result['total'] > 0 else 0
            full_rate = result['full_ok']/result['total']*100 if result['total'] > 0 else 0
            f.write(f"| {ds} | {result['total']} | {fast_rate:.1f}% | {full_rate:.1f}% | {result['fast_avg_time']:.2f}s | {result['full_avg_time']:.2f}s |\n")

        f.write(f"\n**总计**: {total_cases} cases | Fast: {total_fast_ok}/{total_cases} ({total_fast_ok/total_cases*100:.1f}%) | Full: {total_full_ok}/{total_cases} ({total_full_ok/total_cases*100:.1f}%)\n\n")

        # 监控摘要
        f.write("## 📈 监控摘要\n\n")
        f.write(f"- **总用例数**: {total_cases}\n")
        f.write(f"- **成功用例**: {total_fast_ok + total_full_ok - (total_cases - total_fast_ok - total_full_ok)}\n")
        f.write(f"- **失败用例**: {len(monitoring_data['failed_cases'])}\n")
        f.write(f"- **API错误**: {monitoring_data['error_count']}\n")
        f.write(f"- **超时用例**: {len(monitoring_data['slow_cases'])}\n")
        f.write(f"- **平均响应时间**: {statistics.mean(monitoring_data['response_times']):.2f}s\n")

        if monitoring_data['error_types']:
            f.write("\n**错误类型分布**:\n")
            for error_type, count in monitoring_data['error_types'].items():
                f.write(f"- {error_type}: {count}\n")

        # 失败案例分析
        f.write("\n## ❌ 失败案例详情\n\n")
        for ds, result in results.items():
            failed_cases = [r for r in result['details'] if not r['fast_ok'] or not r['full_ok']]
            if failed_cases:
                f.write(f"### {ds}\n\n")
                for case in failed_cases:
                    status = []
                    if not case['fast_ok']: status.append("Fast失败")
                    if not case['full_ok']: status.append("Full失败")
                    f.write(f"- **{case['id']}** ({', '.join(status)}): {case['fast_pred'][:100]}...\n")
                f.write("\n")

if __name__ == "__main__":
    run_full_test()