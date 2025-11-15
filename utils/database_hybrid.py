"""
Database Híbrido: PostgreSQL para persistência + JSON para dados temporários

- PostgreSQL: assinaturas, cargos de mediador, canais de resultados
- JSON: filas, apostas ativas, timestamps (dados temporários/voláteis)
"""
import os
import logging
from typing import Dict, List, Optional
from models.bet import Bet
from datetime import datetime, timedelta

logger = logging.getLogger('bot')


class HybridDatabase:
    """Usa PostgreSQL para dados persistentes e JSON para dados temporários"""
    
    def __init__(self):
        # Importa os backends
        from utils.database import Database as JSONDatabase
        from utils.database_pg import PostgresDatabase
        
        self._json_db = JSONDatabase()
        self._pg_db = PostgresDatabase()
        
        logger.info("📊 Database Híbrido: PostgreSQL (persistência) + JSON (temporário)")
    
    # ===== MÉTODOS DE PERSISTÊNCIA (PostgreSQL) =====
    
    def create_subscription(self, guild_id: int, duration_seconds: int = None):
        """Cria ou atualiza uma assinatura (PostgreSQL)"""
        return self._pg_db.create_subscription(guild_id, duration_seconds)
    
    def get_subscription(self, guild_id: int) -> Optional[dict]:
        """Retorna a assinatura de um servidor (PostgreSQL)"""
        return self._pg_db.get_subscription(guild_id)
    
    def is_subscription_active(self, guild_id: int) -> bool:
        """Verifica se um servidor tem assinatura ativa (PostgreSQL)"""
        return self._pg_db.is_subscription_active(guild_id)
    
    def get_all_subscriptions(self) -> dict:
        """Retorna todas as assinaturas (PostgreSQL)"""
        return self._pg_db.get_all_subscriptions()
    
    def get_expired_subscriptions(self) -> List[int]:
        """Retorna lista de guild_ids com assinaturas expiradas (PostgreSQL)"""
        return self._pg_db.get_expired_subscriptions()
    
    def remove_subscription(self, guild_id: int):
        """Remove a assinatura de um servidor (PostgreSQL)"""
        return self._pg_db.remove_subscription(guild_id)
    
    def set_mediator_role(self, guild_id: int, role_id: int):
        """Define o cargo de mediador para um servidor (PostgreSQL)"""
        return self._pg_db.set_mediator_role(guild_id, role_id)
    
    def get_mediator_role(self, guild_id: int) -> Optional[int]:
        """Retorna o ID do cargo de mediador (PostgreSQL)"""
        return self._pg_db.get_mediator_role(guild_id)
    
    def set_results_channel(self, guild_id: int, channel_id: int):
        """Define o canal de resultados (PostgreSQL)"""
        return self._pg_db.set_results_channel(guild_id, channel_id)
    
    def get_results_channel(self, guild_id: int) -> Optional[int]:
        """Retorna o ID do canal de resultados (PostgreSQL)"""
        return self._pg_db.get_results_channel(guild_id)
    
    # ===== MÉTODOS DE METADADOS DE FILA (PostgreSQL) =====
    # Metadados precisam persistir para evitar filas "inválidas"
    
    def save_queue_metadata(self, message_id: int, mode: str, bet_value: float, mediator_fee: float, channel_id: int, currency_type: str = "sonhos"):
        """Salva metadados de uma fila (PostgreSQL + JSON backup)"""
        # Salva no PostgreSQL (persistente)
        self._pg_db.save_queue_metadata(message_id, mode, bet_value, mediator_fee, channel_id, currency_type)
        # Backup no JSON para compatibilidade
        self._json_db.save_queue_metadata(message_id, mode, bet_value, mediator_fee, channel_id, currency_type)
    
    def get_queue_metadata(self, message_id: int) -> Optional[dict]:
        """Retorna metadados de uma fila (PostgreSQL com fallback JSON + sincronização)"""
        # Tenta buscar no PostgreSQL primeiro
        pg_metadata = self._pg_db.get_queue_metadata(message_id)
        json_metadata = self._json_db.get_queue_metadata(message_id)
        
        # Se tem no PostgreSQL mas não no JSON, sincroniza
        if pg_metadata and not json_metadata:
            logger.info(f"🔄 Sincronizando metadata {message_id}: PostgreSQL -> JSON")
            self._json_db.save_queue_metadata(
                message_id,
                pg_metadata['mode'],
                pg_metadata['bet_value'],
                pg_metadata['mediator_fee'],
                pg_metadata['channel_id'],
                pg_metadata.get('currency_type', 'sonhos')
            )
            return pg_metadata
        
        # Se tem no JSON mas não no PostgreSQL, sincroniza
        if json_metadata and not pg_metadata:
            logger.info(f"🔄 Sincronizando metadata {message_id}: JSON -> PostgreSQL")
            self._pg_db.save_queue_metadata(
                message_id,
                json_metadata['mode'],
                json_metadata['bet_value'],
                json_metadata['mediator_fee'],
                json_metadata['channel_id'],
                json_metadata.get('currency_type', 'sonhos')
            )
            return json_metadata
        
        # Se tem em ambos, retorna PostgreSQL (fonte de verdade)
        if pg_metadata:
            return pg_metadata
        
        # Se não tem em nenhum, retorna None
        return None
    
    def get_all_queue_metadata(self) -> dict:
        """Retorna todos os metadados de filas (PostgreSQL com fallback JSON)"""
        # Busca do PostgreSQL
        pg_metadata = self._pg_db.get_all_queue_metadata()
        # Merge com JSON (JSON tem prioridade para dados mais recentes)
        json_metadata = self._json_db.get_all_queue_metadata()
        pg_metadata.update(json_metadata)
        return pg_metadata
    
    def delete_queue_metadata(self, message_id: int):
        """Remove metadados de uma fila (PostgreSQL + JSON)"""
        self._pg_db.delete_queue_metadata(message_id)
        self._json_db.delete_queue_metadata(message_id)
    
    # ===== MÉTODOS TEMPORÁRIOS (JSON) =====
    # Filas, apostas ativas, timestamps - não precisam persistir entre deploys
    
    def add_to_queue(self, queue_id: str, user_id: int):
        """Adiciona um jogador à fila (JSON)"""
        return self._json_db.add_to_queue(queue_id, user_id)
    
    def remove_from_queue(self, queue_id: str, user_id: int):
        """Remove um jogador da fila (JSON)"""
        return self._json_db.remove_from_queue(queue_id, user_id)
    
    def get_queue(self, queue_id: str) -> List[int]:
        """Retorna a fila de um painel específico (JSON)"""
        return self._json_db.get_queue(queue_id)
    
    def remove_from_all_queues(self, user_id: int):
        """Remove um jogador de todas as filas (JSON)"""
        return self._json_db.remove_from_all_queues(user_id)
    
    def is_user_in_active_bet(self, user_id: int) -> bool:
        """Verifica se um jogador está em uma aposta ativa (JSON)"""
        return self._json_db.is_user_in_active_bet(user_id)
    
    def add_active_bet(self, bet: Bet):
        """Adiciona uma aposta ativa (JSON)"""
        return self._json_db.add_active_bet(bet)
    
    def get_active_bet(self, bet_id: str) -> Optional[Bet]:
        """Retorna uma aposta ativa pelo ID (JSON)"""
        return self._json_db.get_active_bet(bet_id)
    
    def get_bet_by_channel(self, channel_id: int) -> Optional[Bet]:
        """Retorna uma aposta pelo ID do canal (JSON)"""
        return self._json_db.get_bet_by_channel(channel_id)
    
    def update_active_bet(self, bet: Bet):
        """Atualiza uma aposta ativa (JSON)"""
        return self._json_db.update_active_bet(bet)
    
    def finish_bet(self, bet: Bet):
        """Finaliza uma aposta e move para o histórico (JSON)"""
        return self._json_db.finish_bet(bet)
    
    def get_bet_history(self) -> List[Bet]:
        """Retorna o histórico de apostas (JSON)"""
        return self._json_db.get_bet_history()
    
    def get_all_active_bets(self) -> Dict[str, Bet]:
        """Retorna todas as apostas ativas (JSON)"""
        return self._json_db.get_all_active_bets()
    
    def get_expired_queue_players(self, timeout_minutes: int = 5):
        """Retorna jogadores que estão há mais de X minutos na fila (JSON)"""
        return self._json_db.get_expired_queue_players(timeout_minutes)
    
    def get_all_queue_ids(self) -> List[str]:
        """Retorna todos os IDs de filas existentes (JSON)"""
        return self._json_db.get_all_queue_ids()
    
    def cleanup_orphaned_data(self):
        """Remove dados órfãos (JSON)"""
        return self._json_db.cleanup_orphaned_data()
    
    def _load_data(self) -> dict:
        """Carrega dados do arquivo JSON (para compatibilidade)"""
        return self._json_db._load_data()
    
    def _save_data(self, data: dict):
        """Salva dados no arquivo JSON (para compatibilidade)"""
        return self._json_db._save_data(data)
