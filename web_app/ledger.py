import hashlib
import json
import time
from models import db, LedgerBlock

class BlockchainLedger:
    def __init__(self):
        pass

    @staticmethod
    def calculate_hash(index, timestamp, data, previous_hash):
        value = str(index) + str(timestamp) + json.dumps(data, sort_keys=True) + str(previous_hash)
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def create_genesis_block(self):
        # check if blockchain is empty
        if LedgerBlock.query.count() == 0:
            genesis_block = LedgerBlock(
                index=0,
                timestamp=time.time(),
                data={'message': 'Genesis Block'},
                previous_hash='0',
                hash=self.calculate_hash(0, time.time(), {'message': 'Genesis Block'}, '0')
            )
            db.session.add(genesis_block)
            db.session.commit()

    def add_block(self, data):
        last_block = LedgerBlock.query.order_by(LedgerBlock.index.desc()).first()
        if not last_block:
            self.create_genesis_block()
            last_block = LedgerBlock.query.order_by(LedgerBlock.index.desc()).first()

        new_index = last_block.index + 1
        new_timestamp = time.time()
        new_hash = self.calculate_hash(new_index, new_timestamp, data, last_block.hash)

        new_block = LedgerBlock(
            index=new_index,
            timestamp=new_timestamp,
            data=data,
            previous_hash=last_block.hash,
            hash=new_hash
        )
        db.session.add(new_block)
        db.session.commit()
        return new_block

    def verify_chain_integrity(self):
        blocks = LedgerBlock.query.order_by(LedgerBlock.index.asc()).all()
        for i in range(1, len(blocks)):
            current = blocks[i]
            previous = blocks[i-1]

            if current.hash != self.calculate_hash(current.index, current.timestamp, current.data, current.previous_hash):
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

ledger = BlockchainLedger()
