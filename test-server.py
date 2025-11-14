#!/usr/bin/env python3
"""
Script de teste para verificar se o servidor HTTP está funcionando
"""
import asyncio
from aiohttp import web
import os

async def ping(request):
    return web.Response(text="pong", status=200)

async def health(request):
    return web.Response(text="Bot Status: OK\nUptime: OK", status=200)

async def main():
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    app.router.add_get('/ping', ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"✅ Servidor de teste rodando em http://0.0.0.0:{port}")
    print(f"   Teste: curl http://localhost:{port}/ping")
    print(f"   Teste: curl http://localhost:{port}/health")
    print("")
    print("Pressione Ctrl+C para parar")
    
    # Manter rodando
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado")

if __name__ == "__main__":
    asyncio.run(main())
