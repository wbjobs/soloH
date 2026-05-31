from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TxInputCreate(BaseModel):
    txId: str = Field(description="交易ID")
    vout: int = Field(description="输出索引")
    scriptSig: Optional[str] = Field(default=None, description="签名脚本")
    sequence: Optional[int] = Field(default=None, description="序列号")


class TxInputResponse(BaseModel):
    id: int = Field(description="输入ID")
    txId: str = Field(description="交易ID")
    vout: int = Field(description="输出索引")
    scriptSig: Optional[str] = Field(default=None, description="签名脚本")
    sequence: Optional[int] = Field(default=None, description="序列号")
    prevTxId: Optional[str] = Field(default=None, description="前一个交易ID")
    prevAddress: Optional[str] = Field(default=None, description="前一个地址")
    prevValue: Optional[float] = Field(default=None, description="前一个金额")

    class Config:
        from_attributes = True


class TxOutputCreate(BaseModel):
    value: float = Field(description="金额")
    scriptPubKey: Optional[str] = Field(default=None, description="公钥脚本")
    address: Optional[str] = Field(default=None, description="地址")
    type: Optional[str] = Field(default=None, description="输出类型")


class TxOutputResponse(BaseModel):
    id: int = Field(description="输出ID")
    txId: str = Field(description="交易ID")
    n: int = Field(description="输出索引")
    value: float = Field(description="金额")
    scriptPubKey: Optional[str] = Field(default=None, description="公钥脚本")
    address: Optional[str] = Field(default=None, description="地址")
    type: Optional[str] = Field(default=None, description="输出类型")
    isSpent: bool = Field(default=False, description="是否已花费")
    spentTxId: Optional[str] = Field(default=None, description="花费的交易ID")

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    txId: str = Field(description="交易ID")
    hash: Optional[str] = Field(default=None, description="哈希")
    version: Optional[int] = Field(default=None, description="版本")
    size: Optional[int] = Field(default=None, description="大小")
    vsize: Optional[int] = Field(default=None, description="虚拟大小")
    weight: Optional[int] = Field(default=None, description="权重")
    lockTime: Optional[int] = Field(default=None, description="锁定时间")
    blockHash: Optional[str] = Field(default=None, description="区块哈希")
    blockHeight: Optional[int] = Field(default=None, description="区块高度")
    blockTime: Optional[datetime] = Field(default=None, description="区块时间")
    confirmations: Optional[int] = Field(default=None, description="确认数")
    inputs: List[TxInputCreate] = Field(default_factory=list, description="输入列表")
    outputs: List[TxOutputCreate] = Field(default_factory=list, description="输出列表")


class TransactionResponse(BaseModel):
    id: int = Field(description="交易数据库ID")
    txId: str = Field(description="交易ID")
    hash: Optional[str] = Field(default=None, description="哈希")
    version: Optional[int] = Field(default=None, description="版本")
    size: Optional[int] = Field(default=None, description="大小")
    vsize: Optional[int] = Field(default=None, description="虚拟大小")
    weight: Optional[int] = Field(default=None, description="权重")
    lockTime: Optional[int] = Field(default=None, description="锁定时间")
    blockHash: Optional[str] = Field(default=None, description="区块哈希")
    blockHeight: Optional[int] = Field(default=None, description="区块高度")
    blockTime: Optional[datetime] = Field(default=None, description="区块时间")
    confirmations: Optional[int] = Field(default=None, description="确认数")
    inputCount: int = Field(description="输入数量")
    outputCount: int = Field(description="输出数量")
    inputValue: float = Field(description="输入总金额")
    outputValue: float = Field(description="输出总金额")
    fee: Optional[float] = Field(default=None, description="手续费")
    inputs: List[TxInputResponse] = Field(default_factory=list, description="输入列表")
    outputs: List[TxOutputResponse] = Field(default_factory=list, description="输出列表")
    suspiciousScore: Optional[float] = Field(default=None, description="可疑分数")

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    id: int = Field(description="交易数据库ID")
    txId: str = Field(description="交易ID")
    blockHeight: Optional[int] = Field(default=None, description="区块高度")
    blockTime: Optional[datetime] = Field(default=None, description="区块时间")
    inputCount: int = Field(description="输入数量")
    outputCount: int = Field(description="输出数量")
    inputValue: float = Field(description="输入总金额")
    outputValue: float = Field(description="输出总金额")
    fee: Optional[float] = Field(default=None, description="手续费")
    suspiciousScore: Optional[float] = Field(default=None, description="可疑分数")

    class Config:
        from_attributes = True


class BlockCreate(BaseModel):
    blockHash: str = Field(description="区块哈希")
    height: int = Field(description="区块高度")
    version: Optional[int] = Field(default=None, description="版本")
    previousBlockHash: Optional[str] = Field(default=None, description="前一区块哈希")
    merkleRoot: Optional[str] = Field(default=None, description="默克尔根")
    time: Optional[datetime] = Field(default=None, description="时间")
    bits: Optional[str] = Field(default=None, description="难度位")
    nonce: Optional[int] = Field(default=None, description="随机数")
    difficulty: Optional[float] = Field(default=None, description="难度")
    txCount: Optional[int] = Field(default=None, description="交易数量")
    size: Optional[int] = Field(default=None, description="大小")
    weight: Optional[int] = Field(default=None, description="权重")


class BlockResponse(BaseModel):
    id: int = Field(description="区块数据库ID")
    blockHash: str = Field(description="区块哈希")
    height: int = Field(description="区块高度")
    version: Optional[int] = Field(default=None, description="版本")
    previousBlockHash: Optional[str] = Field(default=None, description="前一区块哈希")
    merkleRoot: Optional[str] = Field(default=None, description="默克尔根")
    time: Optional[datetime] = Field(default=None, description="时间")
    bits: Optional[str] = Field(default=None, description="难度位")
    nonce: Optional[int] = Field(default=None, description="随机数")
    difficulty: Optional[float] = Field(default=None, description="难度")
    txCount: Optional[int] = Field(default=None, description="交易数量")
    size: Optional[int] = Field(default=None, description="大小")
    weight: Optional[int] = Field(default=None, description="权重")

    class Config:
        from_attributes = True


class AddressCreate(BaseModel):
    address: str = Field(description="地址")
    type: Optional[str] = Field(default=None, description="地址类型")
    scriptPubKey: Optional[str] = Field(default=None, description="公钥脚本")
    pubKey: Optional[str] = Field(default=None, description="公钥")
    isMine: bool = Field(default=False, description="是否为自有地址")
    label: Optional[str] = Field(default=None, description="标签")


class AddressResponse(BaseModel):
    id: int = Field(description="地址数据库ID")
    address: str = Field(description="地址")
    type: Optional[str] = Field(default=None, description="地址类型")
    scriptPubKey: Optional[str] = Field(default=None, description="公钥脚本")
    pubKey: Optional[str] = Field(default=None, description="公钥")
    isMine: bool = Field(default=False, description="是否为自有地址")
    label: Optional[str] = Field(default=None, description="标签")
    received: float = Field(default=0, description="接收总金额")
    sent: float = Field(default=0, description="发送总金额")
    balance: float = Field(default=0, description="余额")
    txCount: int = Field(default=0, description="交易数量")
    firstSeen: Optional[datetime] = Field(default=None, description="首次出现时间")
    lastSeen: Optional[datetime] = Field(default=None, description="最后出现时间")
    suspiciousScore: Optional[float] = Field(default=None, description="可疑分数")

    class Config:
        from_attributes = True


class AddressListResponse(BaseModel):
    id: int = Field(description="地址数据库ID")
    address: str = Field(description="地址")
    type: Optional[str] = Field(default=None, description="地址类型")
    label: Optional[str] = Field(default=None, description="标签")
    balance: float = Field(default=0, description="余额")
    txCount: int = Field(default=0, description="交易数量")
    suspiciousScore: Optional[float] = Field(default=None, description="可疑分数")

    class Config:
        from_attributes = True
