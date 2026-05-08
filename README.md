# Green Receipt API

AI-powered environmental forensic receipt backend for the [Monad Hackathon](https://monad.xyz/).

Users submit a product name (e.g. `"Nike Pegasus Trail 5 DV3865-602"`).  
The backend:

1. Calls AI to gather public environmental evidence
2. Hashes each evidence item with **keccak256**
3. Builds a **Merkle Tree** from evidence hashes
4. Hashes the full report JSON → `reportHash`
5. Saves report + ERC-721 metadata to local files
6. Mints a **GreenReceiptNFT** on **Monad**
7. Returns the complete receipt to the frontend

---

## Project Structure

```
eco-receipt-api/
├── app/
│   ├── main.py                  # FastAPI app + routes
│   ├── config.py                # Settings (pydantic-settings + .env)
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models
│   ├── services/
│   │   ├── ai_service.py        # Mock / OpenAI report generation
│   │   ├── evidence_service.py  # Evidence hashing pipeline
│   │   ├── hash_service.py      # keccak256 utilities
│   │   ├── merkle_service.py    # Binary Merkle tree
│   │   ├── storage_service.py   # Local JSON storage (swap for IPFS)
│   │   └── web3_service.py      # Web3.py + GreenReceiptNFT contract
│   └── data/
│       ├── reports/             # Saved full report JSONs
│       └── metadata/            # Saved ERC-721 metadata JSONs
├── abi/
│   └── GreenReceiptNFT.json     # Contract ABI
├── .env.example
├── requirements.txt
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable          | Description                                    | Default                          |
|-------------------|------------------------------------------------|----------------------------------|
| `MONAD_RPC_URL`   | Monad JSON-RPC endpoint                        | `https://testnet-rpc.monad.xyz`  |
| `CHAIN_ID`        | Monad chain ID                                 | `10143`                          |
| `CONTRACT_ADDRESS`| Deployed GreenReceiptNFT address               | *(required for mint)*            |
| `PRIVATE_KEY`     | Deployer / auditor private key (0x-prefixed)   | *(required for mint)*            |
| `AI_MODE`         | `mock` (no API key needed) or `openai`         | `mock`                           |
| `OPENAI_API_KEY`  | OpenAI API key (only needed for `openai` mode) | —                                |
| `OPENAI_MODEL`    | OpenAI model name                              | `gpt-4o-mini`                    |
| `STORAGE_BACKEND` | `local` (file system) or `ipfs` (future)       | `local`                          |
| `DEBUG`           | Enable verbose logging                         | `true`                           |

---

## Installation

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and edit env file
cp .env.example .env
# Edit .env — at minimum set AI_MODE=mock for demo without API keys
```

---

## Running the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: http://localhost:8000/docs  
Health check: http://localhost:8000/health

---

## API Reference

### `POST /api/receipts/analyze`

Generate a Green Receipt report without minting.

**Request**
```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "productUrl": "",
  "brand": "Nike"
}
```

**Response**
```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "summary": "...",
  "findings": ["..."],
  "evidences": [
    {
      "title": "Nike Move to Zero",
      "source": "Nike Official",
      "url": "https://...",
      "excerpt": "...",
      "claim": "...",
      "confidence": "High",
      "hash": "0xabc123..."
    }
  ],
  "reportHash": "0x...",
  "evidenceMerkleRoot": "0x...",
  "reportURI": "local://reports/abc123.json",
  "metadataURI": "local://metadata/abc123_meta.json"
}
```

---

### `POST /api/receipts/mint`

Mint an NFT from pre-computed hashes (use after `/analyze`).

**Request**
```json
{
  "to": "0xRecipientAddress",
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "brand": "Nike",
  "score": 62,
  "grade": "Medium Risk",
  "reportHash": "0x...",
  "evidenceMerkleRoot": "0x...",
  "metadataURI": "local://metadata/abc123_meta.json"
}
```

**Response**
```json
{
  "tokenId": 1,
  "transactionHash": "0x...",
  "contractAddress": "0x..."
}
```

---

### `POST /api/receipts/analyze-and-mint`

Full pipeline in one call.

**Request**
```json
{
  "productName": "Nike Pegasus Trail 5 DV3865-602",
  "productUrl": "",
  "brand": "Nike",
  "to": "0xRecipientAddress"
}
```

**Response** — combined fields from both `/analyze` and `/mint`.

---

## Connecting to Monad

1. Set `MONAD_RPC_URL` to the Monad testnet RPC (e.g. `https://testnet-rpc.monad.xyz`).
2. Set `CHAIN_ID=10143` (Monad testnet).
3. Fund your wallet with Monad testnet tokens.
4. Deploy `GreenReceiptNFT` via Foundry (see [eco-receipt-contracts](https://github.com/Eco-Receipt/eco-receipt-contracts)).
5. Set `CONTRACT_ADDRESS` to the deployed address.
6. Set `PRIVATE_KEY` to the owner/auditor key.

---

## Configuring the Contract ABI

After running `forge build` in the contracts repo, copy the ABI:

```bash
# From eco-receipt-contracts root
cp out/GreenReceiptNFT.sol/GreenReceiptNFT.json \
   ../eco-receipt-api/abi/GreenReceiptNFT.json
```

The `web3_service.py` accepts both a bare JSON array and `{"abi": [...]}` format.

---

## MVP Architecture

```
Frontend
   │
   │  POST /api/receipts/analyze-and-mint
   ▼
FastAPI (main.py)
   │
   ├─ ai_service.py ──────► Mock JSON / OpenAI GPT
   │                         (Tavily / SerpAPI / Exa pluggable here)
   │
   ├─ evidence_service.py ─► hash each evidence (keccak256)
   │                          build Merkle root
   │                          hash full report
   │
   ├─ storage_service.py ──► save report JSON  → app/data/reports/
   │                          save metadata JSON → app/data/metadata/
   │                          (swap for IPFS/Pinata/Arweave)
   │
   └─ web3_service.py ─────► Web3.py → Monad RPC
                              mintReceipt() → GreenReceiptNFT
                              parse ReceiptMinted event → tokenId
```

### Hashing Strategy

- **Evidence hash**: `keccak256(canonical_json_bytes)` — keys sorted, compact separators
- **Report hash**: `keccak256(canonical_json_bytes)` of the full enriched report
- **Merkle tree**: binary tree with sorted sibling pairs (`keccak256(min ++ max)`), odd layers padded by duplicating the last leaf — compatible with OpenZeppelin `MerkleProof`

---

## Adding a Real Search Provider

In `app/services/ai_service.py`, add a new branch in `generate_report()`:

```python
elif mode == "tavily":
    return await _tavily_report(product_name, brand, product_url)
```

Then implement `_tavily_report()` using the [Tavily API](https://docs.tavily.com/) to search for evidence and pass results to the LLM for structuring.

---

## Running in Mock Mode (Demo)

No API keys needed:

```bash
AI_MODE=mock uvicorn app.main:app --reload
```

Call `/api/receipts/analyze` with `"Nike Pegasus Trail 5"` to get rich demo data instantly.
