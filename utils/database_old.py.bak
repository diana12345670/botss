import json
import os
from typing import Dict, List, Optional, Tuple
from models.bet import Bet
from datetime import datetime, timedelta


class Database:
    """Gerencia o armazenamento de dados do bot"""

    def __init__(self, data_dir: str = "data"):
        # Detectar ambiente de produção
        is_flyio = os.getenv("FLY_APP_NAME") is not None
        is_railway = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None

        if is_flyio or is_railway:
            # Em produção (Fly.io ou Railway), usar /app/data
            self.data_dir = "/app/data" if os.path.exists("/app") else data_dir
        else:
            self.data_dir = data_dir

        self.data_file = os.path.join(self.data_dir, "bets.json")

        # Log do caminho do arquivo para debug
        import logging
        logger = logging.getLogger('bot')
        logger.info(f"📁 Banco de dados: {self.data_file}")

        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Garante que o arquivo de dados existe"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_data({'queues': {}, 'queue_timestamps': {}, 'queue_metadata': {}, 'active_bets': {}, 'bet_history': [], 'mediator_roles': {}})

    def _load_data(self) -> dict:
        """Carrega dados do arquivo"""
        import logging
        logger = logging.getLogger('bot')
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Valida estrutura básica
                if not isinstance(data, dict):
                    logger.error(f"❌ Dados corrompidos (não é dict): {type(data)}")
                    raise ValueError("Arquivo de dados corrompido")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao decodificar JSON: {e}")
            logger.warning("🔄 Criando backup e reinicializando dados...")
            # Faz backup do arquivo corrompido
            import shutil
            backup_path = f"{self.data_file}.corrupted.backup"
            shutil.copy2(self.data_file, backup_path)
            logger.info(f"💾 Backup salvo em: {backup_path}")
            # Retorna dados vazios
            return {'queues': {}, 'queue_timestamps': {}, 'queue_metadata': {}, 'active_bets': {}, 'bet_history': [], 'mediator_roles': {}}
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao carregar dados: {e}")
            raise

    def _save_data(self, data: dict):
        """Salva dados no arquivo"""
        import logging
        logger = logging.getLogger('bot')
        
        temp_file = None
        try:
            # Salva em arquivo temporário primeiro (atomic write)
            temp_file = f"{self.data_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Se salvou com sucesso, substitui o arquivo original
            import shutil
            shutil.move(temp_file, self.data_file)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar dados: {e}")
            # Remove arquivo temporário se existir
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            raise

    def add_to_queue(self, queue_id: str, user_id: int):
        """Adiciona um jogador à fila"""
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()
        
        # Inicializa estruturas se não existirem
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
            # Limita o tamanho da fila para evitar memory leaks (máx 10 jogadores)
            if len(data['queues'][queue_id]) >= 10:
                # Remove o jogador mais antigo
                oldest_user = data['queues'][queue_id].pop(0)
                if str(oldest_user) in data['queue_timestamps'][queue_id]:
                    del data['queue_timestamps'][queue_id][str(oldest_user)]
                logger.info(f"🧹 Removido jogador mais antigo {oldest_user} da fila {queue_id}")
            
            data['queues'][queue_id].append(user_id)
            # Armazena o timestamp quando o jogador entra na fila
            data['queue_timestamps'][queue_id][str(user_id)] = datetime.now().isoformat()
            logger.info(f"💾 DB: Usuário {user_id} adicionado à fila {queue_id}")
        else:
            logger.info(f"⚠️ DB: Usuário {user_id} já estava na fila {queue_id}")
        
        self._save_data(data)

    def remove_from_queue(self, queue_id: str, user_id: int):
        """Remove um jogador da fila"""
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()

        # Remove da fila
        if queue_id in data['queues'] and user_id in data['queues'][queue_id]:
            data['queues'][queue_id].remove(user_id)
            logger.info(f"💾 DB: Usuário {user_id} removido da fila {queue_id}")
        else:
            logger.info(f"⚠️ DB: Tentativa de remover {user_id} da fila {queue_id}, mas não estava lá")
            logger.info(f"📊 DB: Fila atual {queue_id}: {data['queues'].get(queue_id, [])}")

        # Garante que queue_timestamps existe
        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}

        # Remove o timestamp
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

    def remove_from_all_queues(self, user_id: int):
        """Remove um jogador de todas as filas"""
        data = self._load_data()
        for mode in data['queues']:
            if user_id in data['queues'][mode]:
                data['queues'][mode].remove(user_id)
        # Remove também dos timestamps
        if 'queue_timestamps' in data:
            for queue_id in data['queue_timestamps']:
                if str(user_id) in data['queue_timestamps'][queue_id]:
                    del data['queue_timestamps'][queue_id][str(user_id)]
        self._save_data(data)

    def is_user_in_active_bet(self, user_id: int) -> bool:
        """Verifica se um jogador está em uma aposta ativa"""
        data = self._load_data()
        for bet_data in data['active_bets'].values():
            if bet_data['player1_id'] == user_id or bet_data['player2_id'] == user_id:
                return True
        return False

    def add_active_bet(self, bet: Bet):
        """Adiciona uma aposta ativa"""
        data = self._load_data()
        bet_dict = bet.to_dict()
        # Garante que valores são float antes de salvar
        bet_dict['bet_value'] = float(bet_dict['bet_value'])
        bet_dict['mediator_fee'] = float(bet_dict['mediator_fee'])
        data['active_bets'][bet.bet_id] = bet_dict
        self._save_data(data)

    def get_active_bet(self, bet_id: str) -> Optional[Bet]:
        """Retorna uma aposta ativa pelo ID"""
        data = self._load_data()
        bet_data = data['active_bets'].get(bet_id)
        if bet_data:
            # Garante conversão float ao carregar
            bet_data['bet_value'] = float(bet_data.get('bet_value', 0))
            bet_data['mediator_fee'] = float(bet_data.get('mediator_fee', 0))
            return Bet.from_dict(bet_data)
        return None

    def get_bet_by_channel(self, channel_id: int) -> Optional[Bet]:
        """Retorna uma aposta pelo ID do canal"""
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()
        logger.info(f"🔍 DB: Buscando aposta para channel_id={channel_id} (type={type(channel_id)})")
        logger.info(f"📊 DB: {len(data['active_bets'])} apostas ativas no banco")
        
        for bet_id, bet_data in data['active_bets'].items():
            stored_channel_id = bet_data.get('channel_id')
            logger.info(f"  - Comparando: {stored_channel_id} (type={type(stored_channel_id)}) == {channel_id} (type={type(channel_id)})?")
            
            # Compara convertendo ambos para int (caso um seja string)
            if int(stored_channel_id) == int(channel_id):
                logger.info(f"✅ DB: Aposta encontrada! bet_id={bet_id}")
                # Garante conversão float ao carregar
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
        """Retorna jogadores que estão há mais de X minutos na fila

        Returns:
            dict: {queue_id: [user_ids]} de jogadores expirados
        """
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
        """Salva metadados de uma fila (mode, bet_value, mediator_fee, channel_id, currency_type)"""
        import logging
        logger = logging.getLogger('bot')
        
        # Validação de entrada
        if not isinstance(message_id, int) or message_id <= 0:
            logger.error(f"❌ message_id inválido: {message_id}")
            raise ValueError(f"message_id deve ser um inteiro positivo, recebido: {message_id}")
        
        if not mode or not isinstance(mode, str):
            logger.error(f"❌ mode inválido: {mode}")
            raise ValueError(f"mode deve ser uma string não vazia, recebido: {mode}")
        
        try:
            bet_value = float(bet_value)
            mediator_fee = float(mediator_fee)
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Valores inválidos: bet_value={bet_value}, mediator_fee={mediator_fee}")
            raise ValueError(f"bet_value e mediator_fee devem ser numéricos: {e}")
        
        if bet_value <= 0:
            logger.error(f"❌ bet_value deve ser positivo: {bet_value}")
            raise ValueError(f"bet_value deve ser maior que zero, recebido: {bet_value}")
        
        if mediator_fee < 0:
            logger.error(f"❌ mediator_fee deve ser não-negativo: {mediator_fee}")
            raise ValueError(f"mediator_fee deve ser >= 0, recebido: {mediator_fee}")
        
        data = self._load_data()
        if 'queue_metadata' not in data:
            data['queue_metadata'] = {}

        queue_id = f"{mode}_{message_id}"
        data['queue_metadata'][str(message_id)] = {
            'queue_id': queue_id,
            'mode': mode,
            'bet_value': bet_value,
            'mediator_fee': mediator_fee,
            'channel_id': int(channel_id),
            'message_id': int(message_id),
            'currency_type': currency_type
        }
        
        logger.info(f"✅ Metadados salvos: queue_id={queue_id}, bet_value={bet_value}, mediator_fee={mediator_fee}, currency={currency_type}")
        self._save_data(data)

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

    def delete_queue_metadata(self, message_id: int):
        """Remove metadados de uma fila"""
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()
        if 'queue_metadata' not in data:
            return

        message_id_str = str(message_id)
        if message_id_str in data['queue_metadata']:
            del data['queue_metadata'][message_id_str]
            self._save_data(data)
            logger.info(f"🗑️ DB: Metadados da mensagem {message_id} removidos")

    def cleanup_orphaned_data(self):
        """Remove dados órfãos (filas vazias, timestamps sem fila, etc.) para economizar espaço"""
        data = self._load_data()
        cleaned = False
        
        # Remove filas vazias
        if 'queues' in data:
            empty_queues = [qid for qid, queue in data['queues'].items() if not queue]
            for qid in empty_queues:
                del data['queues'][qid]
                cleaned = True
        
        # Remove timestamps de filas que não existem mais
        if 'queue_timestamps' in data and 'queues' in data:
            orphaned_timestamps = [qid for qid in data['queue_timestamps'].keys() if qid not in data['queues']]
            for qid in orphaned_timestamps:
                del data['queue_timestamps'][qid]
                cleaned = True
        
        # Remove timestamps de usuários que não estão mais na fila
        if 'queue_timestamps' in data and 'queues' in data:
            for qid in list(data['queue_timestamps'].keys()):
                if qid in data['queues']:
                    queue_users = set(map(str, data['queues'][qid]))
                    timestamp_users = set(data['queue_timestamps'][qid].keys())
                    orphaned_users = timestamp_users - queue_users
                    for user_id in orphaned_users:
                        del data['queue_timestamps'][qid][user_id]
                        cleaned = True
        
        # Limita histórico de apostas a 100 entradas mais recentes
        if 'bet_history' in data and len(data['bet_history']) > 100:
            data['bet_history'] = data['bet_history'][-100:]
            cleaned = True
        
        if cleaned:
            self._save_data(data)
            return True
        return False

    def create_subscription(self, guild_id: int, duration_seconds: int = None):
        """Cria ou atualiza uma assinatura para um servidor
        
        Args:
            guild_id: ID do servidor
            duration_seconds: Duração em segundos (None = permanente)
        """
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()
        if 'subscriptions' not in data:
            data['subscriptions'] = {}
        
        subscription = {
            'guild_id': guild_id,
            'permanent': duration_seconds is None,
            'created_at': datetime.now().isoformat()
        }
        
        if duration_seconds is not None:
            expires_at = datetime.now() + timedelta(seconds=duration_seconds)
            subscription['expires_at'] = expires_at.isoformat()
            logger.info(f"📝 Assinatura criada para guild {guild_id} até {expires_at}")
        else:
            subscription['expires_at'] = None
            logger.info(f"♾️ Assinatura permanente criada para guild {guild_id}")
        
        data['subscriptions'][str(guild_id)] = subscription
        self._save_data(data)

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
        import logging
        logger = logging.getLogger('bot')
        
        data = self._load_data()
        if 'subscriptions' not in data:
            return
        
        guild_id_str = str(guild_id)
        if guild_id_str in data['subscriptions']:
            del data['subscriptions'][guild_id_str]
            self._save_data(data)
            logger.info(f"🗑️ Assinatura removida para guild {guild_id}")