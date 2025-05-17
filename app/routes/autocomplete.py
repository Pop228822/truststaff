import os
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import httpx

router = APIRouter()

DADATA_TOKEN = os.getenv("DADATA_TOKEN")

@router.get("/autocomplete/orgs")
async def autocomplete_orgs(query: str = Query(..., min_length=2)):
    """
    Прокси-эндпоинт для автокомплита организаций.
    Клиент шлёт ?query=..., а сервер обращается к DaData (type=party).
    """
    if not DADATA_TOKEN:
        raise HTTPException(status_code=500, detail="DaData token not configured")

    # Формируем запрос к API DaData
    # Документация: https://dadata.ru/api/suggest/party/
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
    headers = {
        "Authorization": f"Token {DADATA_TOKEN}",
        "Content-Type": "application/json"
    }
    json_data = {
        "query": query,
        "count": 10
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=json_data)
        data = response.json()

    suggestions = []
    for item in data.get("suggestions", []):
        name = item["value"]  # "ООО "ТЕХНОСТРОЙ ЮГО-ВОСТОК""
        inn = item["data"].get("inn", "")
        address = item["data"].get("address", {}).get("value", "")

        # Формируем общую строку
        # Пример: "ООО "ТЕХНОСТРОЙ ЮГО-ВОСТОК"\n9721070113  г Москва..."
        # Но т.к. \n в HTML будет не виден, можно через " — " или "<br>"
        display = f'{name}\n{inn}  {address}'

        s = {
            "value": name,  # по-прежнему чистое название
            "inn": inn,
            "address": address,
            "display": display,  # новая строка для вывода в подсказке
        }
        suggestions.append(s)

    return {"results": suggestions}
