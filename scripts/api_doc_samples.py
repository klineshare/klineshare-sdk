#!/usr/bin/env python3
"""Live / offline sample helpers for docs/API_USAGE.md generation."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# 字段中文释义（覆盖行情/账户/专题常见字段；未知字段走 _zh_for 启发式）
FIELD_ZH: Dict[str, str] = {
    # 基础
    'symbol': '标的代码', 'ks_code': '标的别名（入参）', 'name': '名称', 'sname': '证券简称',
    'short_name': '简称', 'full_name': '全称', 'english_name': '英文名', 'e_sname': '英文简称',
    'market': '市场', 'exchange': '交易所', 'trade_market': '交易市场', 'board': '板块标识',
    'board_name': '板块名称', 'security': '证券', 'security_type': '证券类型',
    'stock_class': '股票类别', 'type': '类型', 'type_label': '类型说明', 'kind': '种类',
    'category': '分类', 'classification': '分类', 'label': '标签', 'title': '标题',
    'desc': '描述', 'description': '描述', 'intro': '简介', 'introduction': '介绍',
    'id': '编号', 'code': '代码', 'path': '路径', 'tab': '页签/分类', 'group': '分组',
    'group_id': '分组编号', 'group_label': '分组名称', 'rank': '排名', 'status': '状态',
    'success': '是否成功', 'message': '消息', 'version': '版本', 'source': '数据来源',
    'source_label': '来源说明', 'unit': '单位', 'value': '数值', 'values': '数值列表',
    'field': '字段名', 'fields': '字段名列表', 'items': '条目列表', 'data': '业务数据（可展开）',
    'meta': '元信息', 'params': '参数', 'param': '参数', 'query': '查询条件',
    'example': '示例', 'default': '默认值', 'required': '是否必填', 'mode': '模式',
    'format': '载荷格式', 'sep': '列分隔符', 'symbols': '按标的分组的数据',
    # 时间
    'date': '交易日', 'trade_date': '交易日', 'tradedate': '交易日（入参别名）',
    'time': '时分秒', 'timestamp': '时间戳（毫秒）', 'updated_at': '更新时间',
    'update_time': '更新时间', 'update_date': '更新日期', 'captured_at': '采集时间',
    'fetched_at': '拉取时间', 'occurred_at': '发生时间', 'occurred_time': '发生时刻',
    'publish_date': '公告日', 'report_date': '报告期', 'notice_date': '公告日',
    'list_date': '上市日期', 'listing_date': '上市日期', 'founded_date': '成立日期',
    'inception_date': '成立日', 'start_date': '开始日期', 'end_date': '结束日期',
    'start': '开始', 'end': '结束', 'bdate': '开始日', 'edate': '结束日',
    'year': '年份', 'years': '年份列表', 'dates': '日期列表',
    'latest_trading_day': '最近交易日', 'next_trading_day': '下一交易日',
    'recent_trading_days': '近期交易日', 'future_trading_days': '未来交易日',
    'trading_sessions': '交易时段', 'period': '周期（秒）', 'period_days': '周期天数',
    'period_type': '周期类型', 'periods': '周期列表', 'periods_label': '周期说明',
    'count': '条数', 'limit': '条数上限', 'page': '页码', 'offset': '偏移',
    'total': '总数', 'max_count': '最大条数', 'max_minute_count': '分钟线最大条数',
    # 行情价量
    'open': '开盘价', 'high': '最高价', 'low': '最低价', 'close': '收盘价 / 最新价',
    'price': '最新价', 'last': '最新价', 'prev_close': '昨收', 'pre_close': '昨收',
    'avg_price': '均价', 'avg_px': '均价', 'average_px': '均价',
    'volume': '成交量', 'amount': '成交额', 'turnover': '换手相关',
    'turnover_rate': '换手率', 'turnover_ratio': '换手率',
    'change': '涨跌额', 'px_change': '涨跌额', 'pct_chg': '涨跌幅',
    'change_pct': '涨跌幅', 'change_percent': '涨跌幅（%）', 'changeratio': '涨跌幅',
    'px_change_rate': '涨跌幅', 'minute_change_percent': '分时涨跌幅',
    'bid': '买一价', 'ask': '卖一价', 'bid_volume': '买一量', 'ask_volume': '卖一量',
    'pe': '市盈率', 'pb': '市净率', 'eps': '每股收益', 'basic_eps': '基本每股收益',
    'eps_ttm': 'TTM 每股收益', 'eps_last_year': '去年每股收益', 'bps': '每股净资产',
    'bvps': '每股净资产', 'mv': '市值', 'float_mv': '流通市值', 'market_value': '市值',
    'aum': '资产管理规模', 'aum_yi': '规模（亿）', 'capital': '股本',
    'total_shares': '总股本', 'float_shares': '流通股本',
    'a_shares': 'A 股股本', 'b_shares': 'B 股股本', 'h_shares': 'H 股股本',
    'float_a_shares': '流通 A 股', 'float_b_shares': '流通 B 股',
    'indicators': '附加指标', 'adjust_type': '复权类型', 'adjust_types': '可用复权类型',
    # 资金流
    'main_net': '主力净流入', 'main_net_ratio': '主力净流入占比',
    'main_net_5d': '近5日主力净流入', 'main_net_10d': '近10日主力净流入',
    'main_net_ratio_5d': '近5日主力净占比', 'main_net_ratio_10d': '近10日主力净占比',
    'net': '净流入', 'net_10k': '净流入（万元）', 'netamount': '净流入额',
    'buy': '买入额', 'sell': '卖出额', 'inamount': '流入额', 'outamount': '流出额',
    'ratioamount': '净流入占比', 'fund_flow': '资金流向',
    'super_net': '超大单净流入', 'super_net_ratio': '超大单净占比',
    'large_net': '大单净流入', 'large_net_ratio': '大单净占比',
    'medium_net': '中单净流入', 'medium_net_ratio': '中单净占比',
    'small_net': '小单净流入', 'small_net_ratio': '小单净占比',
    'r0': '超大单', 'r0_in': '超大单流入', 'r0_out': '超大单流出',
    'r0_net': '超大单净流入', 'r0_ratio': '超大单净占比',
    'r0_net_3': '近3日超大单净流入', 'r0_net_5': '近5日超大单净流入', 'r0_net_10': '近10日超大单净流入',
    'r0_ratio_3': '近3日超大单净占比', 'r0_ratio_5': '近5日超大单净占比', 'r0_ratio_10': '近10日超大单净占比',
    'r0x_ratio': '超大单占比', 'r0x_ratio_3': '近3日超大单占比',
    'r0x_ratio_5': '近5日超大单占比', 'r0x_ratio_10': '近10日超大单占比',
    'r1': '大单', 'r1_net': '大单净流入', 'r2': '中单', 'r2_net': '中单净流入',
    'r3': '小单', 'r3_in': '小单流入', 'r3_out': '小单流出',
    'r3_net': '小单净流入', 'r3_ratio': '小单净占比',
    'amount_10k_cny': '金额（万元）', 'volume_10k_shares': '成交量（万股）',
    'buy_seats': '买方席位数', 'sell_seats': '卖方席位数',
    'buy_total_10k': '买入合计（万元）', 'sell_total_10k': '卖出合计（万元）',
    'seats': '席位', 'hot_money': '游资', 'traders': '营业部/席位',
    # 涨跌停 / 情绪
    'rise_count': '上涨家数', 'fall_count': '下跌家数', 'limit_up_count': '涨停家数',
    'open_count': '打开次数', 'break_count': '炸板次数', 'stay_count': '封板维持次数',
    'consecutive_days': '连板天数', 'consecutive_down_days': '连续下跌天数',
    'first_sealed_at': '首次封板时间', 'first_sealed_time': '首次封板时刻',
    'last_sealed_at': '最后封板时间', 'last_sealed_time': '最后封板时刻',
    'first_limit_up_at': '首次涨停时间', 'first_limit_up_time': '首次涨停时刻',
    'first_break_at': '首次炸板时间', 'first_break_time': '首次炸板时刻',
    'yesterday_consecutive_days': '昨日连板天数',
    'yesterday_first_sealed_at': '昨日首次封板时间', 'yesterday_first_sealed_time': '昨日首次封板时刻',
    'yesterday_last_sealed_at': '昨日最后封板时间', 'yesterday_last_sealed_time': '昨日最后封板时刻',
    'yesterday_open_count': '昨日打开次数',
    'reason': '涨停/异动原因', 'sentiment': '市场情绪', 'event_type': '事件类型',
    'avg_changeratio': '平均涨跌幅', 'ts_changeratio': '分时涨跌幅',
    'ts_name': '分时名称', 'ts_symbol': '分时标的', 'ts_trade': '分时成交',
    'ts_ratioamount': '分时净流入占比',
    # 板块 / 目录
    'plate': '板块', 'plates': '板块列表', 'plate_id': '板块编号', 'keyword': '关键词',
    'node': '目录节点', 'nodes': '节点列表', 'parent_node': '父节点',
    'is_leaf': '是否叶子节点', 'children': '子节点', 'members': '成分',
    'member_count': '成分数量', 'active_member_count': '活跃成分数',
    'total_member_count': '成分总数', 'stocks': '成分股列表', 'stock_rows': '股票行',
    'board_rows': '板块行', 'boards': '板块列表', 'concepts': '概念列表', 'concept': '概念',
    'industry': '行业', 'csrc_industry': '证监会行业', 'industry_leader': '行业龙头',
    'index_code': '指数代码', 'index_name': '指数名称', 'indices': '指数列表',
    'scope': '范围', 'scope_label': '范围说明', 'list_count': '列表条数',
    # 分红 / 财务摘要
    'dividend': '分红', 'dividend_ratio': '股息率', 'bonus_ratio': '送转比例',
    'bonus_it_ratio': '送转所得税比例', 'it_ratio': '所得税比例',
    'pretax_bonus_rmb': '税前红利（元）', 'per_capital_reserve': '每股资本公积',
    'per_unassign_profit': '每股未分配利润', 'assign_progress': '分红进度',
    'impl_plan_profile': '实施方案概况', 'equity_record_date': '股权登记日',
    'ex_dividend_date': '除权除息日', 'ex_dividend_days': '除权天数',
    'plan_notice_date': '预案公告日', 'pnp_yoy_ratio': '归母净利润同比',
    'bd10_close_adjchrate': '除权前10日复权涨跌幅', 'd10_close_adjchrate': '近10日复权涨跌幅',
    'd30_close_adjchrate': '近30日复权涨跌幅', 'is_kcb': '是否科创板',
    'market_type': '市场类型', 'report_type': '报告类型', 'yoy': '同比',
    'income': '利润表', 'balance': '资产负债表', 'cashflow': '现金流量表',
    'financials': '财务数据', 'reports': '报告列表', 'datasets': '数据集',
    'latest_publish_date': '最近披露日',
    # 账户 / 配额 / 套餐
    'account': '账号信息（文档已脱敏）', 'key': '密钥信息（文档已脱敏）',
    'plan': '套餐', 'main_plan': '主套餐', 'effective_plan': '生效套餐',
    'scopes': '权限范围', 'scope_rows': '权限明细行', 'limits': '限额',
    'channels': '订阅频道', 'level2_channels': 'Level2 频道',
    'endpoint_access_status': '接口权限状态', 'subscription_summary': '订阅摘要',
    'subscription_active': '订阅是否生效', 'main_expires_at': '主套餐到期时间',
    'main_role_id': '主角色 ID', 'effective_role_id': '生效角色 ID',
    'kline': 'K 线能力说明', 'realtime': '实时行情能力', 'realtime_feature_gates': '实时附加字段门控',
    'realtime_batch_limits': '实时批量上限', 'market_flash_trial': '市场快讯试用额度',
    'live_kline_bar_quota_note': '实时 K 线额度说明', 'symbol_quota_note': '标的配额说明',
    'symbol_quota_base': '标的配额基数', 'symbol_quota_total': '标的配额合计',
    'symbol_quota_limits': '标的配额明细', 'symbol_quota_stacks': '标的配额叠加项',
    'max_realtime_symbols': '实时行情最大标的数', 'max_symbols_per_minute': '每分钟最大标的数',
    'max_level2_slots': 'Level2 最大槽位', 'max_level2_subscriptions': 'Level2 最大订阅数',
    'max_level2_symbols': 'Level2 最大标的数', 'max_live_kline_bars_per_minute': '每分钟实时 K 线条数上限',
    'max_abnormal_events_subscriptions': '异动事件最大订阅数',
    'max_futures_stream_subscriptions': '期货推流最大订阅数',
    'max_market_flash_subscriptions': '市场快讯最大订阅数',
    'max_realtime_stream_subscriptions': '实时推流最大订阅数',
    'max_realtime_stream_symbols': '实时推流最大标的数',
    'rate_limit': '限速配置', 'rate_limit_per_minute': '每分钟请求上限',
    'rate_limit_global': '全局限速', 'requests': '请求数', 'requests_per_minute': '每分钟请求数',
    'api_surface': 'API 能力面', 'market_indices': '市场指数清单',
    'register_roles': '可注册角色', 'tier_columns': '套餐对比列',
    'tier_compare_note': '套餐对比说明', 'tier_id': '套餐档位 ID', 'tier_name': '套餐档位名',
    'tier_names': '档位名称列表', 'tier_names_trial': '试用档位名', 'tier_rank': '档位排序',
    'tier_version': '档位版本', 'tier_poster': '档位海报', 'tiers': '套餐档位',
    'access_mode': '访问模式（trial/locked/open）', 'allowed': '是否允许',
    'allowed_indicators': '允许的附加指标', 'allowed_indicators_label': '附加指标说明',
    'availability': '可用性', 'available': '是否可用', 'trial': '试用',
    'daily_limit': '日限额', 'max_uses': '最大次数', 'used_today': '今日已用',
    'remaining': '剩余次数', 'exhausted': '是否用尽', 'used_in_window': '窗口内已用',
    'window_minutes': '统计窗口（分钟）', 'max_symbols': '最大标的数',
    'allow_pagination': '是否支持分页', 'required_plan': '所需套餐',
    'policy': '策略', 'policy_label': '策略说明', 'policy_note': '策略备注',
    'scopes_label': '权限说明', 'scopes_added_label': '新增权限说明',
    'endpoints': '接口列表', 'routes': '路由', 'contact': '联系方式',
    # ETF / 基金
    'fund_type': '基金类型', 'fund_subtype': '基金子类型', 'manager_name': '基金经理',
    'manager_company': '管理人', 'custodian': '托管人', 'management_fee': '管理费',
    'custodian_fee': '托管费', 'invest_scope': '投资范围', 'invest_target': '投资目标',
    'benchmark': '业绩比较基准', 'distribution': '分红方式', 'distribution_ratio': '分红比例',
    'premium': '溢价率', 'discount_percent': '折价率', 'discount_label': '折溢价说明',
    'scale_style': '规模风格', 'finance_style': '财务风格',
    # 排名 / 涨跌幅区间
    'rank_today': '今日排名', 'rank_5d': '近5日排名', 'rank_10d': '近10日排名',
    'change_5d': '近5日涨跌幅', 'change_10d': '近10日涨跌幅',
    'avg_price_5d': '近5日均价', 'avg_volume_10d': '近10日均量',
    'close_price_days_ago': 'N 日前收盘价',
    # 其他常见
    'trade': '是否交易日', 'trade_status': '交易状态', 'trading': '交易中',
    'quote_ready': '行情是否就绪', 'is_active': '是否有效', 'is_new': '是否新股/新条',
    'is_primary': '是否主条目', 'core_flag': '核心标记', 'height': '高度/连板高度',
    'stage': '阶段', 'factor': '因子', 'metric_pct': '指标百分比', 'metrics': '指标集',
    'snapshot': '快照', 'cells': '单元格', 'visible_keys': '可见字段',
    'top_buy_stocks': '买入前排股票', 'related_codes': '关联代码',
    'related_securities': '关联证券', 'former_names': '曾用名',
    'company': '公司', 'website': '官网', 'email': '邮箱', 'phone': '电话', 'fax': '传真',
    'zip_code': '邮编', 'office_address': '办公地址', 'registered_address': '注册地址',
    'registered_capital': '注册资本', 'registered_capital_currency': '注册资本币种',
    'currency': '币种', 'currencies': '币种列表', 'organization_form': '组织形式',
    'main_business': '主营业务', 'management': '管理层', 'secretary': '董秘',
    'underwriter': '承销商', 'broker': '券商', 'institution_type': '机构类型',
    'ipo_price': '发行价', 'placing_price': '配售价', 'placing_ratio': '配售比例',
    'original_price': '原价', 'original_price_display': '原价展示', 'price_display': '价格展示',
    'price_period': '价格周期', 'premium_date': '溢价日期',
    'enter_date': '入选日期', 'exit_date': '剔除日期',
    'suspend_end': '停牌结束', 'suspend_expire': '停牌到期',
    'transfer_flag': '转板标记', 'audit_status': '审核状态',
    'disclosure_url': '披露链接', 'governance_documents': '治理文件',
    'symbol_format': '代码格式', 'symbol_format_note': '代码格式说明',
    'captured_at_format': '采集时间格式', 'captured_at_format_note': '采集时间格式说明',
    'date_field': '日期字段名', 'value_fields': '数值字段', 'period_fields': '周期字段',
    'field_meta': '字段元数据', 'default_sort': '默认排序', 'sort_order': '排序方向',
    'sort_note': '排序说明', 'sorts': '可选排序', 'stock_sorts': '股票排序项',
    'included': '是否纳入', 'has_basic': '是否含基础字段', 'max_indicator_specs': '最大指标规格数',
    'rate_limits_text': '限速说明文本', 'indices_refreshed_at': '指数刷新时间',
    'etf_realtime': 'ETF 实时', 'index_realtime': '指数实时', 'futures': '期货',
    'hk': '港股相关', 'a': 'A 股相关', 'b': 'B 股相关', 'h': 'H 股相关',
    'addend': '加项', 'multiplier': '乘数', 'first': '首项', 'standard': '标准值',
    'predict_resume': '预计复牌', 'operation_type': '操作类型',
    'cate_type': '分类类型', 'cate_na': '分类名称', 'cate_ra': '分类比率',
    'cnt_r0x_ratio': '超大单占比计数', 'net_in': '净流入（别名）',
}

# 财报科目等全大写代码：给出可读前缀，避免一律「见文档」
_FIN_CODE_HINT = '财报科目代码'

# 嵌套列表字段：样例表里单独展开
_EXPAND_LIST_KEYS = (
    'data', 'items', 'stocks', 'stock_rows', 'nodes', 'children', 'members',
    'boards', 'board_rows', 'plates', 'concepts', 'endpoints', 'scopes',
    'scope_rows', 'tiers', 'tier_columns', 'symbols', 'fields', 'reports',
    'datasets', 'indices', 'market_indices', 'realtime_feature_gates',
    'realtime_batch_limits', 'register_roles', 'api_surface', 'seats',
    'traders', 'top_buy_stocks', 'related_securities', 'values',
)

MAX_TABLE_ROWS = 5
MAX_TABLE_COLS = 12
MAX_CELL = 48
MAX_LIST_KEEP = 20  # when normalizing huge lists for storage
MAX_NEST_DEPTH = 2

# 写入文档前脱敏：账号/密钥 + 商业定价/订阅内部字段（不误伤行情 name 等）
_SENSITIVE_KEYS = frozenset({
    'api_key', 'token', 'secret', 'password', 'email', 'phone',
    'authorization', 'access_token', 'refresh_token',
})
# 整段遮罩（定价/订阅摘要等）；叶子价字段不全局遮罩，以免误伤行情里的折溢价字段
_SENSITIVE_NEST = frozenset({
    'account', 'key', 'billing', 'payment',
    'subscription_summary', 'tiers', 'tier_poster', 'register_roles',
})


def _is_sensitive_key(key: str) -> bool:
    low = key.lower()
    if low in _SENSITIVE_KEYS or low in _SENSITIVE_NEST:
        return True
    return any(low.endswith(s) or low.startswith(s) for s in (
        'api_key', 'access_token', 'secret_',
    ))


def _sanitize(obj: Any, *, depth: int = 0) -> Any:
    """脱敏账号/密钥与商业字段，避免写入公开 SDK 文档。"""
    if depth > 6:
        return '…'
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            ks = str(k)
            low = ks.lower()
            if low in _SENSITIVE_NEST:
                out[ks] = '***'
            elif _is_sensitive_key(ks) and not isinstance(v, (dict, list)):
                out[ks] = '***'
            else:
                out[ks] = _sanitize(v, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [_sanitize(x, depth=depth + 1) for x in obj[:MAX_LIST_KEEP]]
    return obj


def doc_sample_stub(name: str) -> Optional[str]:
    """若该接口不应固化完整 live 快照，返回替代说明；否则 None。"""
    if name in ('me', 'refresh_limits'):
        return (
            '文档不固化完整 `/v1/me` 快照（含套餐价、角色 ID、配额叠加等）。\n'
            '请用 `pro.me()` / `pro.refresh_limits()` / `pro.limits.summary()` '
            '查看当前 Key 的权限与限额。'
        )
    if name == 'public_catalog':
        return (
            '文档不固化完整 `/public/v1/catalog` 价目与档位表。\n'
            '请用 `pro.public_catalog()` 或站点文档查看最新档位与 scope 矩阵。'
        )
    return None


@dataclass
class LiveSample:
    name: str
    ok: bool
    verified: bool
    detail: str = ''
    title: str = ''
    data: Any = None
    fields: Tuple[str, ...] = ()
    optional: bool = False
    elapsed: float = 0.0
    source: str = ''  # live | cache | static | skipped


@dataclass
class FetchReport:
    samples: Dict[str, LiveSample] = field(default_factory=dict)
    fetched: int = 0
    verified_ok: int = 0
    failed: int = 0
    skipped: int = 0
    optional_fail: int = 0

    def summary_lines(self) -> List[str]:
        lines = [
            f'样例拉取：成功 {self.fetched}，核对通过 {self.verified_ok}，'
            f'失败 {self.failed}，可选失败 {self.optional_fail}，跳过 {self.skipped}',
        ]
        # 可选失败原因归类，便于看终端
        reasons: Dict[str, int] = {}
        for s in self.samples.values():
            if s.ok and s.verified:
                continue
            if s.source == 'skipped':
                reasons['推流/订阅跳过'] = reasons.get('推流/订阅跳过', 0) + 1
                continue
            d = s.detail or ''
            if '403' in d or 'AuthError' in d or '无 ' in d:
                key = '403 无权限'
            elif '503' in d or '暂不可用' in d:
                key = '503 暂不可用'
            elif '500' in d or '内部错误' in d:
                key = '500 服务端'
            elif '400' in d or '缺少' in d or '须' in d or '不是' in d:
                key = '400 参数/标的'
            elif '404' in d or '未找到' in d or '不存在' in d:
                key = '404 未找到'
            else:
                key = '其他'
            reasons[key] = reasons.get(key, 0) + 1
        if reasons:
            parts = ', '.join(f'{k}={v}' for k, v in sorted(reasons.items()))
            lines.append(f'未嵌入样例归因：{parts}')
        return lines


def load_dotenv(root: Path) -> None:
    root = root.resolve()
    for path in (root / '.env',):
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            k, v = k.strip(), v.strip().strip("'").strip('"')
            if k and k not in os.environ:
                os.environ[k] = v


def build_client(root: Path):
    root = root.resolve()
    load_dotenv(root)
    from klineshare import Client

    key = (os.getenv('KLINESHARE_API_KEY') or os.getenv('L2_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('缺少 API Key：设置 KLINESHARE_API_KEY 或 L2_API_KEY')
    base = (os.getenv('KLINESHARE_BASE_URL') or os.getenv('L2_API_BASE') or '').strip()
    kwargs: dict = dict(
        api_key=key,
        as_dataframe=False,
        limits='off',  # 文档采样不走限额门闩，避免裁切干扰样例
        on_rate_limit='wait',
    )
    if base:
        kwargs['base_url'] = base
    return Client(**kwargs)


def _to_plain(obj: Any) -> Any:
    try:
        import pandas as pd

        if isinstance(obj, pd.DataFrame):
            return obj.head(MAX_LIST_KEEP).to_dict('records')
        if isinstance(obj, pd.Series):
            return obj.head(MAX_LIST_KEEP).to_dict()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in list(obj.items())[:80]}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in list(obj)[:MAX_LIST_KEEP]]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)[:200]


def _zh_for(key: str) -> str:
    """字段中文释义：词典优先，其次启发式，避免一律「见文档」。"""
    if key in FIELD_ZH:
        return FIELD_ZH[key]
    # 数字日期列（如财报多期列头）
    if key.isdigit() and len(key) in (6, 8):
        return f'报告期 {key}'
    if key.isdigit():
        return f'数值列 {key}'
    # 全大写财报科目
    if key.isupper() and key.isalpha() and len(key) >= 3:
        return f'{_FIN_CODE_HINT}（{key}）'
    low = key.lower()
    # 常见后缀
    rules = (
        ('_percent', '百分比'), ('_pct', '百分比'), ('_ratio', '占比/比率'),
        ('_rate', '比率'), ('_count', '数量'), ('_at', '时间'),
        ('_time', '时刻'), ('_date', '日期'), ('_days', '天数'),
        ('_net', '净流入'), ('_in', '流入'), ('_out', '流出'),
        ('_price', '价格'), ('_px', '价格'), ('_name', '名称'),
        ('_code', '代码'), ('_id', '编号'), ('_label', '说明'),
        ('_note', '备注'), ('_limit', '上限'), ('_type', '类型'),
        ('_status', '状态'), ('_shares', '股数'), ('_fee', '费用'),
    )
    for suf, zh in rules:
        if low.endswith(suf) and low != suf[1:]:
            head = key[: -len(suf)]
            return f'{head}（{zh}）' if head else zh
    if low.startswith('max_'):
        return f'上限：{key[4:]}'
    if low.startswith('is_'):
        return f'是否{key[3:]}'
    if low.startswith('avg_'):
        return f'平均{key[4:]}'
    if low.startswith('total_'):
        return f'合计{key[6:]}'
    return f'字段 `{key}`'


def _is_list_of_dicts(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and isinstance(v[0], dict)


def _should_expand(key: str, v: Any, *, depth: int) -> bool:
    """list[dict] 一律展开；中等大小 dict（或白名单键）展开。"""
    if depth >= MAX_NEST_DEPTH:
        return False
    if _is_list_of_dicts(v):
        return True
    if isinstance(v, dict) and v:
        if str(key) in _EXPAND_LIST_KEYS or len(v) <= 24:
            return True
    return False


def _fields_of(data: Any, *, depth: int = 0) -> Tuple[str, ...]:
    """收集字段名；dict 内可展开嵌套一并收录为 parent.child。"""
    keys: List[str] = []

    def _add(k: str) -> None:
        if k not in keys:
            keys.append(k)

    if isinstance(data, list) and data and isinstance(data[0], dict):
        for row in data[:50]:
            if not isinstance(row, dict):
                continue
            for k in row:
                _add(str(k))
        return tuple(keys)

    if isinstance(data, dict):
        for k in data.keys():
            _add(str(k))
        if depth < MAX_NEST_DEPTH:
            for ek, sub in data.items():
                ek_s = str(ek)
                if not _should_expand(ek_s, sub, depth=depth):
                    continue
                if _is_list_of_dicts(sub):
                    for sk in _fields_of(sub, depth=depth + 1):
                        _add(f'{ek_s}.{sk}')
                elif isinstance(sub, dict):
                    for sk in _fields_of(sub, depth=depth + 1):
                        _add(f'{ek_s}.{sk}')
        return tuple(keys)
    return ()


def verify_payload(data: Any, *, kind: str, name: str) -> Tuple[bool, str]:
    """核对返回是否可用作文档样例。"""
    if data is None:
        return False, '返回 None'
    if kind == 'text' or isinstance(data, str):
        if not str(data).strip():
            return False, '空字符串'
        return True, f'str len={len(str(data))}'
    if isinstance(data, list):
        if len(data) == 0:
            # 部分专题接口非交易时段可能为空
            return True, 'list 空（已记录）'
        first = data[0]
        if isinstance(first, dict) and not first:
            return False, 'list[0] 为空对象'
        return True, f'list len={len(data)} fields={list(_fields_of(data))[:8]}'
    if isinstance(data, dict):
        if not data:
            return False, '空对象'
        return True, f'dict keys={list(data.keys())[:10]}'
    return True, type(data).__name__


def _pick_sample_case(entry: Any) -> Optional[Any]:
    """选一次适合拉样例的调用：优先可 live 的非全市场用例。"""
    cases = list(entry.cases)
    non_escape = [c for c in cases if c.style != 'escape']

    def _is_heavy(c: Any) -> bool:
        label = (c.label or '') + str(getattr(c, 'expect_params', '') or '')
        return '全市场' in label or (isinstance(c.expect_params, dict) and c.expect_params.get('all') in (1, True, '1'))

    # 1) live=True 且非全市场
    for c in non_escape:
        if c.live and not _is_heavy(c):
            return c
    # 2) 任意非全市场
    for c in non_escape:
        if not _is_heavy(c):
            return c
    # 3) 退回 direct
    for c in non_escape:
        if c.style == 'direct':
            return c
    return non_escape[0] if non_escape else None


def _cell(v: Any, *, max_len: int = MAX_CELL, will_expand: bool = False) -> str:
    if v is None:
        return ''
    if isinstance(v, float):
        s = f'{v:.6g}'
    elif isinstance(v, list):
        if will_expand or _is_list_of_dicts(v):
            s = f'[{len(v)} 项，见下方展开]'
        elif not v:
            s = '[]'
        elif all(isinstance(x, (str, int, float, bool)) or x is None for x in v[:8]):
            s = json.dumps(v[:8], ensure_ascii=False)
            if len(v) > 8:
                s = s[:-1] + ', …]'
        else:
            s = f'[{len(v)} 项]'
    elif isinstance(v, dict):
        if will_expand:
            s = '{%d 字段，见下方展开}' % len(v)
        else:
            s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace('|', '\\|').replace('\n', ' ')
    if len(s) > max_len:
        s = s[: max_len - 1] + '…'
    return s


def _render_list_of_dicts(rows: List[Any], *, title: str = '') -> List[str]:
    lines: List[str] = []
    dict_rows = [r for r in rows if isinstance(r, dict)]
    if not dict_rows:
        return lines
    if title:
        lines.append(f'**{title}**')
        lines.append('')
    cols = list(_fields_of(dict_rows))[:MAX_TABLE_COLS]
    lines.append('| ' + ' | '.join(f'`{c}`' for c in cols) + ' |')
    lines.append('| ' + ' | '.join('---' for _ in cols) + ' |')
    for row in dict_rows[:MAX_TABLE_ROWS]:
        lines.append('| ' + ' | '.join(_cell(row.get(c)) for c in cols) + ' |')
    extra = len(dict_rows) - MAX_TABLE_ROWS
    if extra > 0 or len(list(_fields_of(dict_rows))) > MAX_TABLE_COLS:
        lines.append('')
        ncols = len(list(_fields_of(dict_rows)))
        lines.append(
            f'（共 {len(dict_rows)} 行'
            + (f'，表中展示前 {MAX_TABLE_ROWS} 行' if extra > 0 else '')
            + (f'、前 {min(ncols, MAX_TABLE_COLS)}/{ncols} 列' if ncols > MAX_TABLE_COLS else '')
            + '）'
        )
    return lines


def render_data_table(data: Any, *, depth: int = 0) -> List[str]:
    """能表格就表格；dict 内 list[dict] / 嵌套对象自动展开。"""
    lines: List[str] = []

    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data[:MAX_TABLE_ROWS]):
        lines.extend(_render_list_of_dicts(data))
        return lines

    if isinstance(data, dict):
        items = list(data.items())
        expand_parts: List[Tuple[str, Any]] = []
        scalar_items: List[Tuple[str, Any]] = []
        for k, v in items:
            if _should_expand(str(k), v, depth=depth):
                expand_parts.append((str(k), v))
            else:
                scalar_items.append((str(k), v))

        if scalar_items:
            lines.append('| 字段 | 值 |')
            lines.append('|------|-----|')
            for k, v in scalar_items[:50]:
                lines.append(f'| `{k}` | {_cell(v)} |')
            if len(scalar_items) > 50:
                lines.append('')
                lines.append(f'（共 {len(scalar_items)} 个顶层字段，表中展示前 50 个）')

        for k, v in expand_parts:
            lines.append('')
            if isinstance(v, list):
                lines.extend(_render_list_of_dicts(v, title=f'`{k}` 展开（{len(v)} 条）'))
            elif isinstance(v, dict):
                lines.append(f'**`{k}` 展开**')
                lines.append('')
                nested = render_data_table(v, depth=depth + 1)
                lines.extend(nested if nested else [
                    '```json',
                    json.dumps(_to_plain(v), ensure_ascii=False, indent=2),
                    '```',
                ])
        if lines:
            return lines

        lines.append('```json')
        lines.append(json.dumps(_to_plain(data), ensure_ascii=False, indent=2))
        lines.append('```')
        return lines

    if isinstance(data, list) and data and all(
        isinstance(x, (str, int, float, bool)) or x is None for x in data[:20]
    ):
        lines.append('| # | 值 |')
        lines.append('|---|-----|')
        for i, v in enumerate(data[:MAX_TABLE_ROWS]):
            lines.append(f'| {i} | {_cell(v)} |')
        if len(data) > MAX_TABLE_ROWS:
            lines.append('')
            lines.append(f'（共 {len(data)} 项，表中展示前 {MAX_TABLE_ROWS} 项）')
        return lines

    if isinstance(data, str):
        text_s = data if len(data) <= 800 else data[:800] + '…'
        lines.append('```text')
        lines.append(text_s)
        lines.append('```')
        return lines

    lines.append('```json')
    lines.append(json.dumps(_to_plain(data), ensure_ascii=False, indent=2))
    lines.append('```')
    return lines


def render_field_table(fields: Sequence[str], data: Any = None) -> List[str]:
    if not fields:
        fields = _fields_of(data)
    if not fields:
        return []

    example: Dict[str, Any] = {}
    nested_example: Dict[str, Any] = {}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        example = data[0]
    elif isinstance(data, dict):
        example = data
        for ek, sub in data.items():
            if _is_list_of_dicts(sub):
                nested_example[str(ek)] = sub[0]
            elif isinstance(sub, dict) and _should_expand(str(ek), sub, depth=0):
                nested_example[str(ek)] = sub

    lines = [
        '**字段说明**',
        '',
        '| 字段 | 含义 | 样例值 |',
        '|------|------|--------|',
    ]
    shown = 0
    for f in fields:
        if shown >= 60:
            break
        if '.' in f:
            parent, child = f.split('.', 1)
            zh = f'{_zh_for(parent)} → {_zh_for(child)}'
            sample_val = ''
            ne = nested_example.get(parent)
            if isinstance(ne, dict):
                sample_val = _cell(ne.get(child))
        else:
            zh = _zh_for(f)
            raw = example.get(f) if f in example else None
            expand = f in nested_example or _should_expand(f, raw, depth=0)
            sample_val = _cell(raw, will_expand=expand) if f in example else ''
        lines.append(f'| `{f}` | {zh} | {sample_val} |')
        shown += 1
    if len(fields) > shown:
        lines.append('')
        lines.append(f'（共 {len(fields)} 个字段，表中展示前 {shown} 个）')
    lines.append('')
    return lines


def fetch_samples(
    pro: Any,
    matrix: Iterable[Any],
    *,
    include_stream: bool = False,
    pause: float = 0.05,
) -> FetchReport:
    report = FetchReport()
    for entry in matrix:
        name = entry.name
        kind = entry.kind
        optional = False

        if kind in ('sse', 'ws', 'local') and not include_stream:
            report.samples[name] = LiveSample(
                name=name, ok=False, verified=False,
                detail='推流/订阅类默认跳过（可用 --include-stream）',
                title='需在线订阅',
                optional=True, source='skipped',
            )
            report.skipped += 1
            continue

        case = _pick_sample_case(entry)
        if case is None:
            report.samples[name] = LiveSample(
                name=name, ok=False, verified=False,
                detail='无可用调用用例', title='无样例', source='skipped',
            )
            report.skipped += 1
            continue

        optional = bool(case.optional_live) or kind in ('sse', 'ws', 'local')
        t0 = time.time()
        try:
            raw = case.call(pro)
            # 迭代器类：只取一条
            if hasattr(raw, '__iter__') and not isinstance(raw, (list, dict, str, bytes)):
                try:
                    raw = next(iter(raw))
                except StopIteration:
                    raw = []
            data = _sanitize(_to_plain(raw))
            elapsed = time.time() - t0
            ok_v, detail = verify_payload(data, kind=kind, name=name)
            fields = _fields_of(data)
            sample = LiveSample(
                name=name,
                ok=True,
                verified=ok_v,
                detail=detail,
                title='返回样例',
                data=data,
                fields=fields,
                optional=optional,
                elapsed=elapsed,
                source='live',
            )
            report.samples[name] = sample
            report.fetched += 1
            if ok_v:
                report.verified_ok += 1
            else:
                if optional:
                    report.optional_fail += 1
                else:
                    report.failed += 1
            flag = 'OK' if ok_v else 'FAIL'
            print(f'  [{flag}] {name} ({elapsed:.2f}s) {detail}'[:200])
        except Exception as exc:  # noqa: BLE001 — 文档生成需吞掉单接口失败
            elapsed = time.time() - t0
            msg = f'{type(exc).__name__}: {exc}'
            report.samples[name] = LiveSample(
                name=name, ok=False, verified=False, detail=msg,
                title='拉取失败', optional=optional, elapsed=elapsed, source='live',
            )
            if optional:
                report.optional_fail += 1
                print(f'  [SKIP] {name} ({elapsed:.2f}s) {msg}'[:200])
            else:
                report.failed += 1
                print(f'  [FAIL] {name} ({elapsed:.2f}s) {msg}'[:200])
        if pause:
            time.sleep(pause)
    return report


def save_cache(path: Path, report: FetchReport) -> None:
    blob = {}
    for name, s in report.samples.items():
        if not s.ok or not s.verified:
            continue
        blob[name] = {
            'title': s.title,
            'data': s.data,
            'fields': list(s.fields),
            'detail': s.detail,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding='utf-8')


def load_cache(path: Path) -> Dict[str, LiveSample]:
    if not path.is_file():
        return {}
    blob = json.loads(path.read_text(encoding='utf-8'))
    out: Dict[str, LiveSample] = {}
    for name, item in blob.items():
        data = _sanitize(item.get('data'))
        out[name] = LiveSample(
            name=name,
            ok=True,
            verified=True,
            detail=item.get('detail', 'cache'),
            title=item.get('title', '缓存样例'),
            data=data,
            fields=_fields_of(data) or tuple(item.get('fields') or ()),
            source='cache',
        )
    return out
