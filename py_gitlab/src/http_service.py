#!/usr/bin/env python3
import asyncio
import aiohttp
from requests.structures import CaseInsensitiveDict
from src.logger import logger

semaphore = asyncio.Semaphore(value=10)


class HttpService:
    def __init__(self, headers=CaseInsensitiveDict()):
        self.headers = headers
        # TODO pick random
        self.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.0.5) Gecko/2008120121 Firefox/3.0.54"

    async def __request(self, url=None, query_params={}, json_body=None, method="GET"):
        await semaphore.acquire()
        session = aiohttp.ClientSession(headers=self.headers)
        result = None
        try:
            query_params_array = [(k, query_params[k])
                                  for k in query_params.keys()]

            request_kargs = {
                "url": url,
                "params": query_params_array,
                "json": json_body
            }

            response = None
            if method == "GET":
                response = await session.get(**request_kargs)
            elif method == 'POST':
                response = await session.post(**request_kargs)
            elif method == 'PUT':
                response = await session.put(**request_kargs)
            elif method == 'PATCH':
                response = await session.patch(**request_kargs)
            else:
                semaphore.release()
                await session.close()
                raise Exception(f"Unkown request method: {method}")

            logger.debug(response.url)
            if response:
                result = await response.json()
            else:
                await session.close()
                semaphore.release()
                raise Exception("Got empty response")

        except Exception as e:
            logger.error(e)

        await session.close()
        semaphore.release()
        return result

    async def get(self, url=None, query_params={}):
        result = await self.__request(url=url, query_params=query_params, method="GET")
        return result

    async def post(self, url=None, query_params={}, json_body=None):
        result = self.__request(url=url, query_params=query_params,
                                json_body=json_body, method="POST")
        return result

    async def patch(self, url=None, query_params={}, json_body=None):
        result = self.__request(url=url, query_params=query_params,
                                json_body=json_body, method="PATCH")
        return result

    async def put(self, url=None, query_params={}, json_body=None):
        result = self.__request(
            url=url, query_params=query_params, json_body=json_body, method="PUT")
        return result
