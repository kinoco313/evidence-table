import requests
import xml.etree.ElementTree as ET
import pandas as pd
from openai import OpenAI
import streamlit as st

db = "pubmed"
esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
searching_words = """
(New England Journal of Medicine[Journal] OR BMJ[Journal] OR The Lancet[Journal] OR JAMA[Journal] OR Annals of Internal Medicine[Journal] OR Kidney International[Journal] OR Journal of the American Society of Nephrology[Journal] OR American Journal of Kidney Diseases[Journal] OR Clinical Journal of the American Society of Nephrology[Journal] OR Nephrology Dialysis Transplantation[Journal])
AND (glomerular hyperfiltration) AND (cardiovascular disease)
"""
retmax = 5  # 最大10000
retmode = "xml"

columns = ["PMID", "Title", "Journal", "PubYear", "Abstract", "Translated"]

def make_request_url(base_url: str, params: dict[str, str | int]) -> str:
    base_url += "?"
    for k, v in params.items():
        base_url += f"{k}={v}&"
    # 最後の余分な "&" を除く
    url = base_url[: len(base_url) - 1]
    return url

def fetch_xml(base_url: str, params: dict[str, str | int]) -> ET.Element:
    res = requests.get(make_request_url(base_url, params))
    return ET.fromstring(res.text)

def extract_pmids(base_url: str, params: dict[str, str | int]) -> list[str]:
    root = fetch_xml(base_url, params)
    # pmidのリスト
    pmids = [pmid.text for pmid in root.findall(".//Id")]
    print(f"{len(pmids)}件のPubMedIDを取得")
    return pmids

# 検索ワードからPMIDのリストを取得
esearch_params = {"db": db, "term": searching_words, "retmax": retmax}
pmids = extract_pmids(esearch_url, esearch_params)

def gen_evid_tbl(base_url: str, params: dict[str, str | int]) -> pd.DataFrame:
    root = fetch_xml(base_url, params)
    # API key
    with open("apikey.txt", "r") as f:
        api_key = f.readline()
    # PMID,論文タイトル,雑誌タイトル,出版年,アブストを辞書のリストとして格納する
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title = article.findtext(".//ArticleTitle")
        jounal = article.findtext(".//Journal/Title")
        pub_year = article.findtext(".//PubDate/Year")
        abstract = "".join([abst.text for abst in article.findall(".//AbstractText")])
        translated = to_abst_ja(abstract, api_key)
        values = [pmid, title, jounal, pub_year, abstract, translated]
        dic = {k: v for k, v in zip(columns, values)}
        articles.append(dic)
    return pd.DataFrame(articles)

def to_abst_ja(abst: str, api_key: str) -> str:   
    client = OpenAI(api_key=api_key)
    prompt = """
    あなたは{# 役割}です。{# 入力文}を日本語に翻訳してください。

    # 役割
    英語と日本語が堪能な臨床研究の専門家
    
    # 入力文
    """
    prompt += abst
    

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    res = completion.choices[0].message.content
    return res

# エビデンステーブル生成
pmids_csv = ",".join(pmids)
efetch_params = {"db": db, "id": pmids_csv, "retmode": retmode}
evid_tbl = gen_evid_tbl(efetch_url, efetch_params)

# 画面に出力
st.write(evid_tbl)
