# Hybrid Retrieval
# Keyword search (BM25) + meaning search (embeddings), merged with RRF.
# Exact section lookups and old<->new law mapping are added on top.

import math
import os
import re

import numpy as np

from .acts import COMMON_ACTS, NEW_TO_OLD, OLD_TO_NEW
from .corpus import ROOT, load_chunks, load_mapping
from .query import analyse, normalize

INDEX_DIR = os.path.join(ROOT, "data", "index")
EMB_PATH = os.path.join(INDEX_DIR, "embeddings.npy")
IDS_PATH = os.path.join(INDEX_DIR, "corpus_key.txt")
TITLE_PATH = os.path.join(INDEX_DIR, "title_embeddings.npy")
# below this we do not answer (fixed before testing on new questions, see PROJECT_CONTROL.md)
LOW_CONFIDENCE = float(os.environ.get("NYAYA_LOW_CONF", "0.375"))
TITLE_KEY = os.path.join(INDEX_DIR, "title_key.txt")
EMBED_MODEL = "intfloat/multilingual-e5-small"
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

STOP = set("a an the of to in on for and or is are was were be by with as at from that this it its "
           "shall any such which who whom under may not no if than other into upon "
           "there here hi hello hey thanks thank please okay ok yes".split())   # chat words carry no law


class FastBM25:
    # Same scoring as BM25Okapi, but uses an inverted index so a query only touches matching documents
    def __init__(self, docs, k1=1.5, b=0.75, epsilon=0.25):
        self.n = len(docs)
        self.dl = np.array([len(d) for d in docs], dtype=np.float32)
        self.avgdl = float(self.dl.mean())
        index = {}
        for i, d in enumerate(docs):
            counts = {}
            for w in d:
                counts[w] = counts.get(w, 0) + 1
            for w, c in counts.items():
                index.setdefault(w, ([], []))
                index[w][0].append(i)
                index[w][1].append(c)
        self.index = {w: (np.array(ids, dtype=np.int32), np.array(tf, dtype=np.float32)) for w, (ids, tf) in index.items()}
        idf = {w: math.log(self.n - len(v[0]) + 0.5) - math.log(len(v[0]) + 0.5) for w, v in self.index.items()}
        floor = epsilon * (sum(idf.values()) / len(idf))
        self.idf = {w: (v if v > 0 else floor) for w, v in idf.items()}
        self.k1, self.b = k1, b
        self.norm = k1 * (1 - b + b * self.dl / self.avgdl)

    def get_scores(self, query):
        scores = np.zeros(self.n, dtype=np.float32)
        for w in query:
            if w not in self.index:
                continue
            ids, tf = self.index[w]
            scores[ids] += self.idf[w] * tf * (self.k1 + 1) / (tf + self.norm[ids])
        return scores


def corpus_key(chunks):
    # fingerprint of the corpus, so old embeddings are never used with new text
    import hashlib
    h = hashlib.sha1()
    for c in chunks:
        h.update((c["id"] + c["text"]).encode("utf-8"))
    return f"{len(chunks)}-{h.hexdigest()}"


def tokenize(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def passage_text(c):
    return f"{c['act_label']} {c['unit']} {c['section']} {c['title']}. {c['text']}"


class Retriever:
    def __init__(self, use_dense=True, use_rerank=False, use_glossary=True):
        self.use_glossary = use_glossary
        self.chunks = load_chunks()
        self.mapping = load_mapping()
        self.by_section = {}
        for i, c in enumerate(self.chunks):
            self.by_section.setdefault((c["act"], c["section"].upper()), []).append(i)

        # Keyword index
        print("[INFO] Building keyword index...")
        self.bm25 = FastBM25([tokenize(passage_text(c)) for c in self.chunks])

        # Meaning index
        self.embedder = None
        self.emb = None
        if use_dense:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
            if os.path.exists(EMB_PATH) and os.path.exists(IDS_PATH):
                with open(IDS_PATH, encoding="utf-8") as f:
                    if f.read() == corpus_key(self.chunks):
                        self.emb = np.load(EMB_PATH).astype(np.float32)
            if self.emb is None:
                print("[INFO] Building embeddings (one time, a few minutes)...")
                self.emb = self.build_embeddings()
            self.build_title_index()

        self.reranker = None
        if use_rerank:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(RERANK_MODEL, device="cpu")

    def build_embeddings(self):
        texts = ["passage: " + passage_text(c)[:1500] for c in self.chunks]
        emb = self.embedder.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True)
        os.makedirs(INDEX_DIR, exist_ok=True)
        np.save(EMB_PATH, emb.astype(np.float16))
        with open(IDS_PATH, "w", encoding="utf-8") as f:
            f.write(corpus_key(self.chunks))
        return emb.astype(np.float32)

    # Title Index
    # Section titles are short legal names ("Theft", "Snatching"); they match plain questions well
    def build_title_index(self):
        first = [i for i, c in enumerate(self.chunks) if c["part"] == 1 and len(c["title"]) > 3]
        self.title_ids = np.array(first)
        key = corpus_key([self.chunks[i] for i in first])
        if os.path.exists(TITLE_PATH) and os.path.exists(TITLE_KEY):
            with open(TITLE_KEY, encoding="utf-8") as f:
                if f.read() == key:
                    self.title_emb = np.load(TITLE_PATH).astype(np.float32)
                    return
        texts = [f"passage: {self.chunks[i]['title']} ({self.chunks[i]['act_label']})" for i in first]
        self.title_emb = self.embedder.encode(texts, batch_size=128, normalize_embeddings=True, show_progress_bar=True)
        np.save(TITLE_PATH, self.title_emb.astype(np.float16))
        with open(TITLE_KEY, "w", encoding="utf-8") as f:
            f.write(key)

    # Exact Section Lookup
    def lookup(self, act, num):
        return self.by_section.get((act, str(num).upper()), [])

    def mapped(self, act, num):
        """New-law sections for an old one (or the other way)."""
        out = []
        for m in self.mapping.get(f"{act}-{str(num).upper()}", []):
            if m["to_section"]:
                out.append((m["to_act"], str(m["to_section"]).upper(), m))
            else:
                out.append((m["to_act"], None, m))
        return out

    # Main Search
    def search(self, query, k=6, extra_query=None, period=None):
        query = normalize(query)   # e.g. "check bounced" -> "cheque bounced"
        info = analyse(query + " " + (extra_query or ""))
        period = period or info["period"]
        scores = {}
        notes = []

        # 1. exact references always come first
        exact = []
        for act, num in info["refs"]:
            acts = [act] if act else ["BNS", "IPC", "BNSS", "CRPC", "COI"]
            for a in acts:
                ids = self.lookup(a, num)
                if not ids:
                    continue
                exact.extend(ids)
                if a in OLD_TO_NEW or a in NEW_TO_OLD:
                    for to_act, to_num, m in self.mapped(a, num):
                        notes.append(m)
                        if to_num:
                            exact.extend(self.lookup(to_act, to_num))
                if act is None:
                    break
        for rank, i in enumerate(exact):
            scores[i] = scores.get(i, 0) + 1.0 / (1 + rank)

        # 2. keyword + meaning search, merged with RRF
        text = query if not extra_query else f"{query} {extra_query}"
        if self.use_glossary and info["legal_terms"]:
            text = f"{text} ({info['legal_terms']})"
        bm = self.bm25.get_scores(tokenize(text))
        bm_top = np.argsort(-bm)[:60]
        rrf = {}
        for rank, i in enumerate(bm_top):
            if bm[i] > 0:
                rrf[int(i)] = rrf.get(int(i), 0) + 1.0 / (60 + rank)
        dense_best = 0.0
        if self.embedder is not None:
            qv = self.embedder.encode(["query: " + text], normalize_embeddings=True)[0]
            sims = self.emb @ qv
            dn_top = np.argsort(-sims)[:60]
            dense_best = float(sims[dn_top[0]])
            for rank, i in enumerate(dn_top):
                rrf[int(i)] = rrf.get(int(i), 0) + 1.0 / (60 + rank)
            # third list: section titles
            tsims = self.title_emb @ qv
            for rank, j in enumerate(np.argsort(-tsims)[:60]):
                i = int(self.title_ids[j])
                rrf[i] = rrf.get(i, 0) + 1.0 / (60 + rank)

        # 3. small boosts: named acts, common acts, right law period
        for i, s in rrf.items():
            c = self.chunks[i]
            if c["act"] in info["acts"]:
                s *= 1.6
            elif c["act"] in COMMON_ACTS:
                s *= 1.15
            if c["repealed"] and period != "old" and c["act"] not in info["acts"]:
                s *= 0.6
            if not c["repealed"] and period == "old" and c["act"] in NEW_TO_OLD:
                s *= 0.8
            scores[i] = scores.get(i, 0) + s

        ranked = sorted(scores, key=lambda i: -scores[i])

        # 4. optional rerank of the top results
        rr_max = None
        if self.reranker is not None and ranked:
            top = ranked[:20]
            rr = self.reranker.predict([(text, passage_text(self.chunks[i])[:1200]) for i in top])
            rr_max = float(max(rr))
            exact_set = set(exact)
            top = sorted(top, key=lambda i: (i not in exact_set, -float(rr[top.index(i)])))
            ranked = top + ranked[20:]

        # 5. one result per section, keep the best part
        results, seen = [], set()
        for i in ranked:
            c = self.chunks[i]
            key = (c["act"], c["section"])
            if key in seen:
                continue
            seen.add(key)
            results.append(dict(c, score=round(scores[i], 4), exact=i in exact))
            if len(results) >= k:
                break

        conf = self.confidence(results, dense_best, bool(exact), rr_max)
        return {
            "results": results,
            "notes": notes,
            "info": info,
            "period": period,
            "confidence": conf,
            # the question names an area of law and the best match is in that act: not low
            # not "low" when the question names an act found at the top, or uses a known everyday
            # legal phrase ("refused to replace", "cheque bounced"): the person described a real legal issue
            "low_confidence": conf < LOW_CONFIDENCE and not exact
                              and not (results and results[0]["act"] in info["acts"])
                              and not (self.use_glossary and info["legal_terms"]),
        }

    @staticmethod
    def confidence(results, dense_best, has_exact, rr_max=None):
        if not results:
            return 0.0
        if has_exact:
            return 0.95
        if rr_max is not None:
            # reranker score: about -8 (unrelated) to +4 (clear match); -5 maps to 0.375
            return float(max(0.0, min(1.0, (rr_max + 8) / 8)))
        # e5 cosine scores sit around 0.75-0.90; map to 0..1
        return float(max(0.0, min(1.0, (dense_best - 0.78) / 0.10))) if dense_best else 0.5
