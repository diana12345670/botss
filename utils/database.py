"""
Sistema Híbrido de Database - StormBet Apostas
Suporta PostgreSQL (opcional) + JSON (fallback e backup)
Múltiplas camadas de segurança para nunca perder dados
"""

import json
import os
from typing import Dict, List, Optional
from models.bet import Bet
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('bot')


class HybridDatabase:
    """
    Database híbrido com suporte a PostgreSQL opcional e JSON como fallback
    
    Funcionamento:
    1. Se DATABASE_URL existe → usa PostgreSQL como principal
    2. Sempre mantém backup em JSON
    3. Se PostgreSQL falhar → usa JSON automaticamente
    4. Múltiplas camadas de backup para garantir integridade
    """
    
    def __init__(self, data_dir: str = "data"):
        # Detectar ambiente
        self.is_flyio = os.getenv("FLY_APP_NAME") is not None
        self.is_railway = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None
        self.is_render = os.getenv("RENDER") is not None or os.getenv("RENDER_SERVICE_NAME") is not None
        
        # Definir diretório de dados
        if self.is_flyio or self.is_railway or self.is_render:
            self.data_dir = "/app/data" if os.path.exists("/app") else data_dir
        else:
            self.data_dir = data_dir
        
        # Arquivos JSON
        self.data_file = os.path.join(self.data_dir, "bets.json")
        self.backup_file = os.path.join(self.data_dir, "bets.backup.json")
        self.backup2_file = os.path.join(self.data_dir, "bets.backup2.json")
        
        # Verificar se PostgreSQL está disponível
        self.database_url = os.getenv("DATABASE_URL")
        self.use_postgres = self.database_url is not None
        self.pg_conn = None
        
        if self.use_postgres:
            self._init_postgres()
            if self.database_url:
                logger.info(f"🐘 PostgreSQL ativado: {self.database_url[:20]}...")
            logger.info(f"💾 Backup JSON ativo: {self.data_file}")
        else:
            logger.info(f"📁 Modo JSON: {self.data_file}")
            logger.info(f"💾 Sistema de backup triplo ativado")
        
        self._ensure_file_exists()
    
    def _init_postgres(self):
        """Inicializa conexão PostgreSQL e cria tabelas"""
        try:
            import psycopg2
            from psycopg2 import pool  # type: ignore
            
            # Criar pool de conexões para melhor performance
            self.pg_pool = psycopg2.pool.SimpleConnectionPool(  # type: ignore
                1, 10,  # min, max conexões
                self.database_url
            )
            
            # Criar tabelas se não existirem
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Tabela única para armazenar todo o JSON
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS stormbet_data (
                            id INTEGER PRIMARY KEY DEFAULT 1,
                            data JSONB NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT single_row CHECK (id = 1)
                        )
                    """)
                    
                    # Criar índice para busca rápida
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_stormbet_data_updated 
                        ON stormbet_data(updated_at)
                    """)
                    
                    # Inserir dados vazios se não existir
                    cur.execute("""
                        INSERT INTO stormbet_data (id, data) 
                        VALUES (1, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (json.dumps(self._get_empty_data()),))
                    
                    conn.commit()
                    logger.info("✅ Tabelas PostgreSQL criadas/verificadas")
            finally:
                self.pg_pool.putconn(conn)
                
        except ImportError:
            logger.warning("⚠️ psycopg2 não instalado, usando apenas JSON")
            self.use_postgres = False
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar PostgreSQL: {e}")
            logger.warning("⚠️ Fallback para modo JSON")
            self.use_postgres = False
    
    def _get_empty_data(self) -> dict:
        """Retorna estrutura de dados vazia"""
        return {
            'queues': {},
            'queue_timestamps': {},
            'queue_metadata': {},
            'active_bets': {},
            'bet_history': [],
            'mediator_roles': {},
            'results_channels': {},
            'subscriptions': {}
        }
    
    def _ensure_file_exists(self):
        """Garante que arquivos JSON existem"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_json(self._get_empty_data())
    
    def _load_data(self) -> dict:
        """Carrega dados (PostgreSQL se disponível, senão JSON)"""
        # Tentar PostgreSQL primeiro
        if self.use_postgres:
            try:
                data = self._load_from_postgres()
                # Sempre fazer backup em JSON também
                self._save_json_silent(data)
                return data
            except Exception as e:
                logger.error(f"❌ Erro ao carregar do PostgreSQL: {e}")
                logger.warning("⚠️ Usando backup JSON")
        
        # Fallback para JSON
        return self._load_from_json()
    
    def _load_from_postgres(self) -> dict:
        """Carrega dados do PostgreSQL"""
        import psycopg2
        import psycopg2.extras
        conn = self.pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM stormbet_data WHERE id = 1")
                row = cur.fetchone()
                if row and row[0]:
                    data = row[0]
                    # PostgreSQL retorna JSONB como dict automaticamente com psycopg2
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    # Validar estrutura de dados
                    if not isinstance(data, dict):
                        logger.error(f"❌ Dados do PostgreSQL não são dict: {type(data)}")
                        # Tentar recuperar do backup JSON
                        logger.warning("⚠️ Tentando recuperar do backup JSON...")
                        return self._load_from_json()
                    
                    # Garantir que todas as chaves necessárias existem
                    required_keys = ['queues', 'queue_timestamps', 'queue_metadata', 
                                   'active_bets', 'bet_history', 'mediator_roles', 
                                   'results_channels', 'subscriptions']
                    for key in required_keys:
                        if key not in data:
                            data[key] = {} if key != 'bet_history' else []
                    
                    return data
                return self._get_empty_data()
        except Exception as e:
            logger.error(f"❌ Erro ao carregar do PostgreSQL: {e}")
            logger.warning("⚠️ Usando backup JSON como fallback")
            return self._load_from_json()
        finally:
            self.pg_pool.putconn(conn)
    
    def _load_from_json(self) -> dict:
        """Carrega dados do JSON com sistema de backup triplo"""
        files_to_try = [self.data_file, self.backup_file, self.backup2_file]
        
        for file_path in files_to_try:
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if file_path != self.data_file:
                            logger.info(f"📂 Recuperado de backup: {file_path}")
                        return data
                    else:
                        logger.error(f"❌ Dados corrompidos em {file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON inválido em {file_path}: {e}")
                # Fazer backup do arquivo corrompido
                import shutil
                backup_path = f"{file_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(file_path, backup_path)
                logger.info(f"💾 Backup do arquivo corrompido: {backup_path}")
            except Exception as e:
                logger.error(f"❌ Erro ao ler {file_path}: {e}")
        
        # Se todos falharam, retornar dados vazios
        logger.warning("⚠️ Todos os arquivos falharam, iniciando com dados vazios")
        return self._get_empty_data()
    
    def _save_data(self, data: dict):
        """Salva dados (PostgreSQL + JSON para redundância)"""
        # Sempre salvar em JSON primeiro (backup garantido)
        self._save_json(data)
        
        # Se PostgreSQL está ativo, salvar lá também
        if self.use_postgres:
            try:
                self._save_to_postgres(data)
            except Exception as e:
                logger.error(f"❌ Erro ao salvar no PostgreSQL: {e}")
                logger.warning("⚠️ Dados salvos apenas em JSON")
    
    def _save_to_postgres(self, data: dict):
        """Salva dados no PostgreSQL"""
        import psycopg2
        import psycopg2.extras
        
        # Validar que data é um dict
        if not isinstance(data, dict):
            logger.error(f"❌ Tentativa de salvar dados não-dict: {type(data)}")
            raise ValueError(f"Dados devem ser dict, recebido: {type(data)}")
        
        conn = self.pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                # PostgreSQL aceita dict diretamente como JSONB com psycopg2.extras.Json
                cur.execute("""
                    UPDATE stormbet_data 
                    SET data = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                """, (psycopg2.extras.Json(data),))
                conn.commit()
        finally:
            self.pg_pool.putconn(conn)
    
    def _save_json(self, data: dict):
        """Salva em JSON com sistema de backup triplo"""
        import shutil
        
        # Rotação de backups: backup2 <- backup1 <- principal
        if os.path.exists(self.backup_file):
            shutil.copy2(self.backup_file, self.backup2_file)
        if os.path.exists(self.data_file):
            shutil.copy2(self.data_file, self.backup_file)
        
        # Salvar arquivo principal (atomic write)
        temp_file = f"{self.data_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            shutil.move(temp_file, self.data_file)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar JSON: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise
    
    def _save_json_silent(self, data: dict):
        """Salva JSON sem levantar exceções (para backups automáticos)"""
        try:
            self._save_json(data)
        except Exception as e:
            logger.warning(f"⚠️ Falha no backup JSON automático: {e}")
    
    # ==================== MÉTODOS DA API ====================
    # Mantendo compatibilidade total com o código existente
    
    def add_to_queue(self, queue_id: str, user_id: int):
        """Adiciona um jogador à fila"""
        data = self._load_data()
        
        if 'queues' not in data:
            data['queues'] = {}
        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}
        
        if queue_id not in data['queues']:
            data['queues'][queue_id] = []
            logger.info(f"🆕 Nova fila criada: {queue_id}")
        if queue_id not in data['queue_timestamps']:
            data['queue_timestamps'][queue_id] = {}

        if user_id not in data['queues'][queue_id]:
            if len(data['queues'][queue_id]) >= 10:
                oldest_user = data['queues'][queue_id].pop(0)
                if str(oldest_user) in data['queue_timestamps'][queue_id]:
                    del data['queue_timestamps'][queue_id][str(oldest_user)]
                logger.info(f"🧹 Removido jogador mais antigo {oldest_user} da fila {queue_id}")
            
            data['queues'][queue_id].append(user_id)
            data['queue_timestamps'][queue_id][str(user_id)] = datetime.now().isoformat()
            logger.info(f"💾 DB: Usuário {user_id} adicionado à fila {queue_id}")
        else:
            logger.info(f"⚠️ DB: Usuário {user_id} já estava na fila {queue_id}")
        
        self._save_data(data)

    def remove_from_queue(self, queue_id: str, user_id: int):
        """Remove um jogador da fila"""
        data = self._load_data()

        if queue_id in data['queues'] and user_id in data['queues'][queue_id]:
            data['queues'][queue_id].remove(user_id)
            logger.info(f"💾 DB: Usuário {user_id} removido da fila {queue_id}")
        else:
            logger.info(f"⚠️ DB: Tentativa de remover {user_id} da fila {queue_id}, mas não estava lá")

        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}

        if queue_id in data['queue_timestamps']:
            user_id_str = str(user_id)
            if user_id_str in data['queue_timestamps'][queue_id]:
                del data['queue_timestamps'][queue_id][user_id_str]
                logger.info(f"⏱️ DB: Timestamp removido para {user_id} na fila {queue_id}")

        self._save_data(data)

    def get_queue(self, queue_id: str) -> List[int]:
        """Retorna a fila de um painel específico"""
        data = self._load_data()
        return data['queues'].get(queue_id, [])

    def set_queue(self, queue_id: str, users: List[int]):
        """Substitui a fila inteira (preserva ordem)"""
        data = self._load_data()

        if 'queues' not in data:
            data['queues'] = {}
        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}

        data['queues'][queue_id] = list(users)
        if queue_id not in data['queue_timestamps']:
            data['queue_timestamps'][queue_id] = {}

        # Mantém timestamps só para usuários atuais
        now = datetime.now().isoformat()
        new_ts = {}
        for uid in data['queues'][queue_id]:
            uid_str = str(uid)
            new_ts[uid_str] = data['queue_timestamps'][queue_id].get(uid_str, now)
        data['queue_timestamps'][queue_id] = new_ts

        self._save_data(data)

    def remove_from_all_queues(self, user_id: int):
        """Remove um jogador de todas as filas"""
        data = self._load_data()
        for mode in data['queues']:
            if user_id in data['queues'][mode]:
                data['queues'][mode].remove(user_id)
        if 'queue_timestamps' in data:
            for queue_id in data['queue_timestamps']:
                if str(user_id) in data['queue_timestamps'][queue_id]:
                    del data['queue_timestamps'][queue_id][str(user_id)]
        self._save_data(data)

    def is_user_in_active_bet(self, user_id: int) -> bool:
        """Verifica se um jogador está em uma aposta ativa"""
        data = self._load_data()
        for bet_data in data['active_bets'].values():
            try:
                if bet_data.get('player1_id') == user_id or bet_data.get('player2_id') == user_id:
                    return True
                team1_ids = bet_data.get('team1_ids') or []
                team2_ids = bet_data.get('team2_ids') or []
                if user_id in team1_ids or user_id in team2_ids:
                    return True
            except Exception:
                # Em caso de dados corrompidos, não travar o bot
                continue
        return False

    def add_active_bet(self, bet: Bet):
        """Adiciona uma aposta ativa"""
        data = self._load_data()
        bet_dict = bet.to_dict()
        bet_dict['bet_value'] = float(bet_dict['bet_value'])
        bet_dict['mediator_fee'] = float(bet_dict['mediator_fee'])
        data['active_bets'][bet.bet_id] = bet_dict
        self._save_data(data)

    def get_active_bet(self, bet_id: str) -> Optional[Bet]:
        """Retorna uma aposta ativa pelo ID"""
        data = self._load_data()
        bet_data = data['active_bets'].get(bet_id)
        if bet_data:
            bet_data['bet_value'] = float(bet_data.get('bet_value', 0))
            bet_data['mediator_fee'] = float(bet_data.get('mediator_fee', 0))
            return Bet.from_dict(bet_data)
        return None

    def get_bet_by_channel(self, channel_id: int) -> Optional[Bet]:
        """Retorna uma aposta pelo ID do canal"""
        data = self._load_data()
        logger.info(f"🔍 DB: Buscando aposta para channel_id={channel_id}")
        logger.info(f"📊 DB: {len(data['active_bets'])} apostas ativas no banco")
        
        for bet_id, bet_data in data['active_bets'].items():
            stored_channel_id = bet_data.get('channel_id')
            if int(stored_channel_id) == int(channel_id):
                logger.info(f"✅ DB: Aposta encontrada! bet_id={bet_id}")
                bet_data['bet_value'] = float(bet_data.get('bet_value', 0))
                bet_data['mediator_fee'] = float(bet_data.get('mediator_fee', 0))
                return Bet.from_dict(bet_data)
        
        logger.info(f"❌ DB: Nenhuma aposta encontrada para channel_id={channel_id}")
        return None

    def update_active_bet(self, bet: Bet):
        """Atualiza uma aposta ativa"""
        data = self._load_data()
        data['active_bets'][bet.bet_id] = bet.to_dict()
        self._save_data(data)

    def finish_bet(self, bet: Bet):
        """Finaliza uma aposta e move para o histórico"""
        data = self._load_data()
        if bet.bet_id in data['active_bets']:
            del data['active_bets'][bet.bet_id]
            data['bet_history'].append(bet.to_dict())
            self._save_data(data)

    def get_bet_history(self) -> List[Bet]:
        """Retorna o histórico de apostas"""
        data = self._load_data()
        return [Bet.from_dict(bet_data) for bet_data in data['bet_history']]

    def get_all_active_bets(self) -> Dict[str, Bet]:
        """Retorna todas as apostas ativas"""
        data = self._load_data()
        return {bet_id: Bet.from_dict(bet_data) for bet_id, bet_data in data['active_bets'].items()}

    def get_expired_queue_players(self, timeout_minutes: int = 5):
        """Retorna jogadores que estão há mais de X minutos na fila"""
        data = self._load_data()
        expired = {}
        current_time = datetime.now()

        for queue_id, timestamps in data.get('queue_timestamps', {}).items():
            expired_users = []
            for user_id_str, timestamp_str in timestamps.items():
                join_time = datetime.fromisoformat(timestamp_str)
                time_diff = (current_time - join_time).total_seconds() / 60

                if time_diff >= timeout_minutes:
                    expired_users.append(int(user_id_str))

            if expired_users:
                expired[queue_id] = expired_users

        return expired

    def set_mediator_role(self, guild_id: int, role_id: int):
        """Define o cargo de mediador para um servidor"""
        data = self._load_data()
        if 'mediator_roles' not in data:
            data['mediator_roles'] = {}
        data['mediator_roles'][str(guild_id)] = role_id
        self._save_data(data)

    def get_mediator_role(self, guild_id: int):
        """Retorna o ID do cargo de mediador configurado para o servidor"""
        data = self._load_data()
        return data.get('mediator_roles', {}).get(str(guild_id))

    def set_results_channel(self, guild_id: int, channel_id: int):
        """Define o canal de resultados para um servidor"""
        data = self._load_data()
        if 'results_channels' not in data:
            data['results_channels'] = {}
        data['results_channels'][str(guild_id)] = channel_id
        self._save_data(data)

    def get_results_channel(self, guild_id: int):
        """Retorna o ID do canal de resultados configurado para o servidor"""
        data = self._load_data()
        return data.get('results_channels', {}).get(str(guild_id))

    def get_all_queue_ids(self) -> List[str]:
        """Retorna todos os IDs de filas existentes"""
        data = self._load_data()
        return list(data['queues'].keys())

    def save_queue_metadata(self, message_id: int, mode: str, bet_value: float, mediator_fee: float, channel_id: int, currency_type: str = "sonhos"):
        """Salva metadados de uma fila"""
        if not isinstance(message_id, int) or message_id <= 0:
            raise ValueError(f"message_id deve ser um inteiro positivo, recebido: {message_id}")
        
        if not mode or not isinstance(mode, str):
            raise ValueError(f"mode deve ser uma string não vazia, recebido: {mode}")
        
        try:
            bet_value = float(bet_value)
            mediator_fee = float(mediator_fee)
        except (ValueError, TypeError) as e:
            raise ValueError(f"bet_value e mediator_fee devem ser numéricos: {e}")
        
        if bet_value <= 0:
            raise ValueError(f"bet_value deve ser maior que zero, recebido: {bet_value}")
        
        if mediator_fee < 0:
            raise ValueError(f"mediator_fee deve ser >= 0, recebido: {mediator_fee}")
        
        data = self._load_data()
        if 'queue_metadata' not in data:
            data['queue_metadata'] = {}

        queue_id = f"{mode}_{message_id}"
        metadata = {
            'queue_id': queue_id,
            'mode': mode,
            'bet_value': bet_value,
            'mediator_fee': mediator_fee,
            'channel_id': int(channel_id),
            'message_id': int(message_id),
            'currency_type': currency_type
        }
        data['queue_metadata'][str(message_id)] = metadata
        
        logger.info(f"💾 Salvando metadados no banco: queue_id={queue_id}, bet_value={bet_value}, mediator_fee={mediator_fee}, currency={currency_type}")
        self._save_data(data)
        
        # Verificar se foi salvo corretamente
        saved_data = self._load_data()
        if str(message_id) in saved_data.get('queue_metadata', {}):
            logger.info(f"✅ Metadados verificados no banco: {len(saved_data['queue_metadata'])} filas total")
        else:
            logger.error(f"❌ FALHA ao salvar metadados para mensagem {message_id}!")

    def get_queue_metadata(self, message_id: int) -> Optional[dict]:
        """Retorna metadados de uma fila pelo message_id"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            return None
        return data['queue_metadata'].get(str(message_id))

    def get_all_queue_metadata(self) -> dict:
        """Retorna todos os metadados de filas"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            return {}
        return data['queue_metadata']

    def save_panel_metadata(self, message_id: int, panel_type: str, bet_value: float, mediator_fee: float, channel_id: int, currency_type: str = "sonhos"):
        """Salva metadados de um painel unificado (1v1 ou 2v2)."""
        if not isinstance(message_id, int) or message_id <= 0:
            raise ValueError(f"message_id deve ser um inteiro positivo, recebido: {message_id}")
        if panel_type not in ("1v1", "2v2"):
            raise ValueError(f"panel_type inválido: {panel_type}")

        try:
            bet_value = float(bet_value)
            mediator_fee = float(mediator_fee)
        except (ValueError, TypeError) as e:
            raise ValueError(f"bet_value e mediator_fee devem ser numéricos: {e}")

        if bet_value <= 0:
            raise ValueError(f"bet_value deve ser maior que zero, recebido: {bet_value}")
        if mediator_fee < 0:
            raise ValueError(f"mediator_fee deve ser >= 0, recebido: {mediator_fee}")

        data = self._load_data()
        if 'queue_metadata' not in data:
            data['queue_metadata'] = {}

        metadata = {
            'type': 'panel',
            'panel_type': panel_type,
            'bet_value': bet_value,
            'mediator_fee': mediator_fee,
            'channel_id': int(channel_id),
            'message_id': int(message_id),
            'currency_type': currency_type
        }

        data['queue_metadata'][str(message_id)] = metadata
        self._save_data(data)

    def get_panel_metadata(self, message_id: int) -> Optional[dict]:
        """Retorna metadados do painel unificado pelo message_id (se existir)."""
        metadata = self.get_queue_metadata(message_id)
        if not metadata:
            return None
        if metadata.get('type') != 'panel':
            return None
        return metadata

    def delete_queue_metadata(self, message_id: int):
        """Remove metadados de uma fila"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            return

        message_id_str = str(message_id)
        if message_id_str in data['queue_metadata']:
            del data['queue_metadata'][message_id_str]
            self._save_data(data)
            logger.info(f"🗑️ DB: Metadados da mensagem {message_id} removidos")

    def cleanup_orphaned_data(self):
        """Remove dados órfãos para economizar espaço"""
        data = self._load_data()
        cleaned = False
        
        if 'queues' in data:
            empty_queues = [qid for qid, queue in data['queues'].items() if not queue]
            for qid in empty_queues:
                del data['queues'][qid]
                cleaned = True
        
        if 'queue_timestamps' in data and 'queues' in data:
            orphaned_timestamps = [qid for qid in data['queue_timestamps'].keys() if qid not in data['queues']]
            for qid in orphaned_timestamps:
                del data['queue_timestamps'][qid]
                cleaned = True
        
        if 'queue_timestamps' in data and 'queues' in data:
            for qid in list(data['queue_timestamps'].keys()):
                if qid in data['queues']:
                    queue_users = set(map(str, data['queues'][qid]))
                    timestamp_users = set(data['queue_timestamps'][qid].keys())
                    orphaned_users = timestamp_users - queue_users
                    for user_id in orphaned_users:
                        del data['queue_timestamps'][qid][user_id]
                        cleaned = True
        
        if 'bet_history' in data and len(data['bet_history']) > 100:
            data['bet_history'] = data['bet_history'][-100:]
            cleaned = True
        
        if cleaned:
            self._save_data(data)
            return True
        return False

    def create_subscription(self, guild_id: int, duration_seconds: int = None):
        """Cria ou atualiza uma assinatura para um servidor
        
        IMPORTANTE: Sempre cria a nova assinatura ANTES de remover a antiga,
        garantindo que o servidor nunca perca acesso durante a transição.
        """
        data = self._load_data()
        if 'subscriptions' not in data:
            data['subscriptions'] = {}
        
        # Verifica se já existe assinatura ativa
        guild_id_str = str(guild_id)
        old_subscription = data['subscriptions'].get(guild_id_str)
        
        if old_subscription:
            logger.info(f"🔄 Substituindo assinatura existente para guild {guild_id}")
            if old_subscription.get('permanent'):
                logger.info(f"   Antiga: Permanente")
            else:
                old_expires = old_subscription.get('expires_at')
                logger.info(f"   Antiga: Expira em {old_expires}")
        
        # Cria NOVA assinatura (isso garante que o servidor continue ativo)
        subscription = {
            'guild_id': guild_id,
            'permanent': duration_seconds is None,
            'created_at': datetime.now().isoformat()
        }
        
        if duration_seconds is not None:
            expires_at = datetime.now() + timedelta(seconds=duration_seconds)
            subscription['expires_at'] = expires_at.isoformat()
            logger.info(f"✅ Nova assinatura criada para guild {guild_id} até {expires_at}")
        else:
            subscription['expires_at'] = None
            logger.info(f"✅ Nova assinatura PERMANENTE criada para guild {guild_id}")
        
        # Substitui a assinatura antiga pela nova de forma atômica
        data['subscriptions'][guild_id_str] = subscription
        self._save_data(data)
        
        logger.info(f"🔒 Transição de assinatura concluída sem desconexão para guild {guild_id}")

    def get_subscription(self, guild_id: int) -> Optional[dict]:
        """Retorna a assinatura de um servidor"""
        data = self._load_data()
        if 'subscriptions' not in data:
            return None
        return data['subscriptions'].get(str(guild_id))

    def is_subscription_active(self, guild_id: int) -> bool:
        """Verifica se um servidor tem assinatura ativa"""
        subscription = self.get_subscription(guild_id)
        if not subscription:
            return False
        
        if subscription.get('permanent'):
            return True
        
        expires_at = subscription.get('expires_at')
        if not expires_at:
            return False
        
        return datetime.fromisoformat(expires_at) > datetime.now()

    def get_all_subscriptions(self) -> dict:
        """Retorna todas as assinaturas"""
        data = self._load_data()
        return data.get('subscriptions', {})

    def get_expired_subscriptions(self) -> List[int]:
        """Retorna lista de guild_ids com assinaturas expiradas"""
        subscriptions = self.get_all_subscriptions()
        expired = []
        
        for guild_id_str, sub in subscriptions.items():
            if sub.get('permanent'):
                continue
            
            expires_at = sub.get('expires_at')
            if expires_at and datetime.fromisoformat(expires_at) <= datetime.now():
                expired.append(int(guild_id_str))
        
        return expired

    def remove_subscription(self, guild_id: int):
        """Remove a assinatura de um servidor"""
        data = self._load_data()
        if 'subscriptions' not in data:
            return
        
        guild_id_str = str(guild_id)
        if guild_id_str in data['subscriptions']:
            del data['subscriptions'][guild_id_str]
            self._save_data(data)
            logger.info(f"🗑️ Assinatura removida para guild {guild_id}")

    # ==================== CENTRAL DE MEDIADORES ====================

    def save_mediator_central_config(self, guild_id: int, channel_id: int, message_id: int):
        """Salva configuração do central de mediadores para um servidor"""
        data = self._load_data()
        if 'mediator_central' not in data:
            data['mediator_central'] = {}
        
        data['mediator_central'][str(guild_id)] = {
            'channel_id': channel_id,
            'message_id': message_id,
            'mediators': {},  # {user_id: {'joined_at': timestamp, 'pix': pix_key}}
            'created_at': datetime.now().isoformat()
        }
        self._save_data(data)
        logger.info(f"💾 Central de mediadores configurado para guild {guild_id}")

    def get_mediator_central_config(self, guild_id: int) -> Optional[dict]:
        """Retorna configuração do central de mediadores"""
        data = self._load_data()
        return data.get('mediator_central', {}).get(str(guild_id))

    def add_mediator_to_central(self, guild_id: int, user_id: int, pix_key: str) -> bool:
        """Adiciona mediador ao central de espera. Retorna False se central está cheio (10 vagas)"""
        data = self._load_data()
        if 'mediator_central' not in data:
            data['mediator_central'] = {}
        
        guild_str = str(guild_id)
        if guild_str not in data['mediator_central']:
            return False
        
        mediators = data['mediator_central'][guild_str].get('mediators', {})
        
        # Verifica limite de 10 vagas
        if len(mediators) >= 10 and str(user_id) not in mediators:
            return False
        
        mediators[str(user_id)] = {
            'joined_at': datetime.now().isoformat(),
            'pix': pix_key
        }
        data['mediator_central'][guild_str]['mediators'] = mediators
        self._save_data(data)
        logger.info(f"✅ Mediador {user_id} adicionado ao central do guild {guild_id}")
        return True

    def remove_mediator_from_central(self, guild_id: int, user_id: int):
        """Remove mediador do central de espera"""
        data = self._load_data()
        guild_str = str(guild_id)
        
        if 'mediator_central' not in data:
            return
        if guild_str not in data['mediator_central']:
            return
        
        mediators = data['mediator_central'][guild_str].get('mediators', {})
        user_str = str(user_id)
        
        if user_str in mediators:
            del mediators[user_str]
            data['mediator_central'][guild_str]['mediators'] = mediators
            self._save_data(data)
            logger.info(f"🗑️ Mediador {user_id} removido do central do guild {guild_id}")

    def get_mediators_in_central(self, guild_id: int) -> dict:
        """Retorna todos os mediadores no central de espera"""
        data = self._load_data()
        guild_str = str(guild_id)
        
        if 'mediator_central' not in data:
            return {}
        if guild_str not in data['mediator_central']:
            return {}
        
        return data['mediator_central'][guild_str].get('mediators', {})

    def get_first_mediator_from_central(self, guild_id: int) -> Optional[tuple]:
        """Retorna o primeiro mediador da fila (mais antigo) do central (user_id, pix_key) ou None se vazio"""
        mediators = self.get_mediators_in_central(guild_id)
        
        if not mediators:
            return None
        
        # Ordena por joined_at para pegar o primeiro (mais antigo)
        sorted_mediators = sorted(
            mediators.items(),
            key=lambda x: x[1]['joined_at']
        )
        
        user_id_str, data = sorted_mediators[0]
        pix_key = data['pix']
        return (int(user_id_str), pix_key)

    def add_mediator_to_end_of_central(self, guild_id: int, user_id: int, pix_key: str) -> bool:
        """Adiciona mediador ao FINAL da fila do central (novo timestamp). Retorna False se central está cheio"""
        data = self._load_data()
        if 'mediator_central' not in data:
            data['mediator_central'] = {}
        
        guild_str = str(guild_id)
        if guild_str not in data['mediator_central']:
            return False
        
        mediators = data['mediator_central'][guild_str].get('mediators', {})
        
        # Verifica limite de 10 vagas
        if len(mediators) >= 10 and str(user_id) not in mediators:
            return False
        
        # Adiciona com timestamp atual (fica no final da fila)
        mediators[str(user_id)] = {
            'joined_at': datetime.now().isoformat(),
            'pix': pix_key
        }
        data['mediator_central'][guild_str]['mediators'] = mediators
        self._save_data(data)
        logger.info(f"✅ Mediador {user_id} adicionado ao FINAL da fila do central do guild {guild_id}")
        return True

    def get_expired_mediators_in_central(self, guild_id: int, timeout_hours: int = 2) -> List[int]:
        """Retorna lista de mediadores que estão há mais de X horas no central"""
        mediators = self.get_mediators_in_central(guild_id)
        expired = []
        current_time = datetime.now()
        
        for user_id_str, data in mediators.items():
            joined_at = datetime.fromisoformat(data['joined_at'])
            hours_waiting = (current_time - joined_at).total_seconds() / 3600
            
            if hours_waiting >= timeout_hours:
                expired.append(int(user_id_str))
        
        return expired

    def is_mediator_in_central(self, guild_id: int, user_id: int) -> bool:
        """Verifica se um mediador está no central"""
        mediators = self.get_mediators_in_central(guild_id)
        return str(user_id) in mediators

    def save_mediator_pix(self, user_id: int, pix_key: str):
        """Salva a chave PIX de um mediador (global, para próximas vezes)"""
        data = self._load_data()
        if 'mediator_pix_keys' not in data:
            data['mediator_pix_keys'] = {}
        
        data['mediator_pix_keys'][str(user_id)] = pix_key
        self._save_data(data)
        logger.info(f"💾 PIX salvo para mediador {user_id}")

    def get_mediator_pix(self, user_id: int) -> Optional[str]:
        """Retorna a chave PIX salva de um mediador"""
        data = self._load_data()
        return data.get('mediator_pix_keys', {}).get(str(user_id))

    def is_mediator_central_configured(self, guild_id: int) -> bool:
        """Verifica se o central de mediadores está configurado para o servidor"""
        config = self.get_mediator_central_config(guild_id)
        return config is not None

    def delete_mediator_central_config(self, guild_id: int):
        """Remove a configuração do central de mediadores"""
        data = self._load_data()
        guild_str = str(guild_id)
        
        if 'mediator_central' in data and guild_str in data['mediator_central']:
            del data['mediator_central'][guild_str]
            self._save_data(data)
            logger.info(f"🗑️ Central de mediadores removido do guild {guild_id}")


# Alias para compatibilidade com código existente
Database = HybridDatabase
