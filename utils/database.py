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

        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Garante que o arquivo de dados existe"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_data({'queues': {}, 'queue_timestamps': {}, 'queue_metadata': {}, 'active_bets': {}, 'bet_history': [], 'mediator_roles': {}})

    def _load_data(self) -> dict:
        """Carrega dados do arquivo"""
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_data(self, data: dict):
        """Salva dados no arquivo"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_to_queue(self, queue_id: str, user_id: int):
        """Adiciona um jogador à fila"""
        data = self._load_data()
        
        # Inicializa estruturas se não existirem
        if 'queues' not in data:
            data['queues'] = {}
        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}
        
        if queue_id not in data['queues']:
            data['queues'][queue_id] = []
        if queue_id not in data['queue_timestamps']:
            data['queue_timestamps'][queue_id] = {}

        if user_id not in data['queues'][queue_id]:
            # Limita o tamanho da fila para evitar memory leaks (máx 10 jogadores)
            if len(data['queues'][queue_id]) >= 10:
                # Remove o jogador mais antigo
                oldest_user = data['queues'][queue_id].pop(0)
                if str(oldest_user) in data['queue_timestamps'][queue_id]:
                    del data['queue_timestamps'][queue_id][str(oldest_user)]
            
            data['queues'][queue_id].append(user_id)
            # Armazena o timestamp quando o jogador entra na fila
            data['queue_timestamps'][queue_id][str(user_id)] = datetime.now().isoformat()
        
        self._save_data(data)

    def remove_from_queue(self, queue_id: str, user_id: int):
        """Remove um jogador da fila"""
        data = self._load_data()

        # Remove da fila
        if queue_id in data['queues'] and user_id in data['queues'][queue_id]:
            data['queues'][queue_id].remove(user_id)

        # Garante que queue_timestamps existe
        if 'queue_timestamps' not in data:
            data['queue_timestamps'] = {}

        # Remove o timestamp
        if queue_id in data['queue_timestamps']:
            user_id_str = str(user_id)
            if user_id_str in data['queue_timestamps'][queue_id]:
                del data['queue_timestamps'][queue_id][user_id_str]

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
        data['active_bets'][bet.bet_id] = bet.to_dict()
        self._save_data(data)

    def get_active_bet(self, bet_id: str) -> Optional[Bet]:
        """Retorna uma aposta ativa pelo ID"""
        data = self._load_data()
        bet_data = data['active_bets'].get(bet_id)
        return Bet.from_dict(bet_data) if bet_data else None

    def get_bet_by_channel(self, channel_id: int) -> Optional[Bet]:
        """Retorna uma aposta pelo ID do canal"""
        data = self._load_data()
        for bet_data in data['active_bets'].values():
            if bet_data['channel_id'] == channel_id:
                return Bet.from_dict(bet_data)
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

    def get_all_queue_ids(self) -> List[str]:
        """Retorna todos os IDs de filas existentes"""
        data = self._load_data()
        return list(data['queues'].keys())

    def save_queue_metadata(self, message_id: int, mode: str, bet_value: float, mediator_fee: float, channel_id: int):
        """Salva metadados de uma fila (mode, bet_value, mediator_fee, channel_id)"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            data['queue_metadata'] = {}

        queue_id = f"{mode}_{message_id}"
        data['queue_metadata'][str(message_id)] = {
            'queue_id': queue_id,
            'mode': mode,
            'bet_value': bet_value,
            'mediator_fee': mediator_fee,
            'channel_id': channel_id,
            'message_id': message_id
        }
        self._save_data(data)

    def get_queue_metadata(self, message_id: int) -> Optional[dict]:
        """Retorna metadados de uma fila pelo message_id"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            return None
        return data['queue_metadata'].get(str(message_id))

    def delete_queue_metadata(self, message_id: int):
        """Remove metadados de uma fila"""
        data = self._load_data()
        if 'queue_metadata' not in data:
            return

        message_id_str = str(message_id)
        if message_id_str in data['queue_metadata']:
            del data['queue_metadata'][message_id_str]
            self._save_data(data)

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