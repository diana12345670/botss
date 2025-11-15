import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional
from models.bet import Bet
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('bot')


class PostgresDatabase:
    """Gerencia o armazenamento de dados do bot usando PostgreSQL"""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise Exception("DATABASE_URL não encontrada nas variáveis de ambiente")
        
        logger.info(f"📁 Banco de dados: PostgreSQL")
        self._create_tables()

    def _get_connection(self):
        """Cria uma nova conexão com o banco"""
        return psycopg2.connect(self.database_url)

    def _create_tables(self):
        """Cria as tabelas necessárias no banco"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Tabela de assinaturas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        guild_id BIGINT PRIMARY KEY,
                        permanent BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        expires_at TIMESTAMP
                    )
                """)
                
                # Tabela de cargos de mediador
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS mediator_roles (
                        guild_id BIGINT PRIMARY KEY,
                        role_id BIGINT NOT NULL
                    )
                """)
                
                # Tabela de canais de resultados
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS results_channels (
                        guild_id BIGINT PRIMARY KEY,
                        channel_id BIGINT NOT NULL
                    )
                """)
                
                # Tabela de filas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS queues (
                        queue_id VARCHAR(255) PRIMARY KEY,
                        players BIGINT[] NOT NULL DEFAULT '{}'
                    )
                """)
                
                # Tabela de timestamps de fila
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS queue_timestamps (
                        queue_id VARCHAR(255) NOT NULL,
                        user_id BIGINT NOT NULL,
                        joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (queue_id, user_id)
                    )
                """)
                
                # Tabela de metadados de fila
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS queue_metadata (
                        message_id BIGINT PRIMARY KEY,
                        queue_id VARCHAR(255) NOT NULL,
                        mode VARCHAR(50) NOT NULL,
                        bet_value NUMERIC NOT NULL,
                        mediator_fee NUMERIC NOT NULL,
                        channel_id BIGINT NOT NULL,
                        currency_type VARCHAR(50) NOT NULL DEFAULT 'sonhos'
                    )
                """)
                
                # Tabela de apostas ativas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_bets (
                        bet_id VARCHAR(255) PRIMARY KEY,
                        mode VARCHAR(50) NOT NULL,
                        player1_id BIGINT NOT NULL,
                        player2_id BIGINT NOT NULL,
                        mediator_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        bet_value NUMERIC NOT NULL DEFAULT 0,
                        mediator_fee NUMERIC NOT NULL DEFAULT 0,
                        mediator_pix VARCHAR(255),
                        player1_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                        player2_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                        winner_id BIGINT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        finished_at TIMESTAMP,
                        currency_type VARCHAR(50) NOT NULL DEFAULT 'sonhos'
                    )
                """)
                
                # Tabela de histórico de apostas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bet_history (
                        id SERIAL PRIMARY KEY,
                        bet_id VARCHAR(255) NOT NULL,
                        mode VARCHAR(50) NOT NULL,
                        player1_id BIGINT NOT NULL,
                        player2_id BIGINT NOT NULL,
                        mediator_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        bet_value NUMERIC NOT NULL DEFAULT 0,
                        mediator_fee NUMERIC NOT NULL DEFAULT 0,
                        mediator_pix VARCHAR(255),
                        player1_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                        player2_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                        winner_id BIGINT,
                        created_at TIMESTAMP NOT NULL,
                        finished_at TIMESTAMP,
                        currency_type VARCHAR(50) NOT NULL DEFAULT 'sonhos'
                    )
                """)
                
                conn.commit()
                logger.info("✅ Tabelas PostgreSQL criadas/verificadas")

    # Métodos de assinatura
    def create_subscription(self, guild_id: int, duration_seconds: int = None):
        """Cria ou atualiza uma assinatura para um servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if duration_seconds is None:
                    # Assinatura permanente
                    cur.execute("""
                        INSERT INTO subscriptions (guild_id, permanent, expires_at)
                        VALUES (%s, TRUE, NULL)
                        ON CONFLICT (guild_id) 
                        DO UPDATE SET permanent = TRUE, expires_at = NULL, created_at = NOW()
                    """, (guild_id,))
                    logger.info(f"♾️ Assinatura permanente criada para guild {guild_id}")
                else:
                    # Assinatura temporária
                    expires_at = datetime.now() + timedelta(seconds=duration_seconds)
                    cur.execute("""
                        INSERT INTO subscriptions (guild_id, permanent, expires_at)
                        VALUES (%s, FALSE, %s)
                        ON CONFLICT (guild_id) 
                        DO UPDATE SET permanent = FALSE, expires_at = %s, created_at = NOW()
                    """, (guild_id, expires_at, expires_at))
                    logger.info(f"📝 Assinatura criada para guild {guild_id} até {expires_at}")
                conn.commit()

    def get_subscription(self, guild_id: int) -> Optional[dict]:
        """Retorna a assinatura de um servidor"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT guild_id, permanent, created_at, expires_at
                    FROM subscriptions
                    WHERE guild_id = %s
                """, (guild_id,))
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None

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
        
        return expires_at > datetime.now()

    def get_all_subscriptions(self) -> dict:
        """Retorna todas as assinaturas"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM subscriptions")
                results = cur.fetchall()
                return {str(row['guild_id']): dict(row) for row in results}

    def get_expired_subscriptions(self) -> List[int]:
        """Retorna lista de guild_ids com assinaturas expiradas"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT guild_id FROM subscriptions
                    WHERE permanent = FALSE AND expires_at <= NOW()
                """)
                return [row[0] for row in cur.fetchall()]

    def remove_subscription(self, guild_id: int):
        """Remove a assinatura de um servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM subscriptions WHERE guild_id = %s", (guild_id,))
                conn.commit()
                logger.info(f"🗑️ Assinatura removida para guild {guild_id}")

    # Métodos de cargo de mediador
    def set_mediator_role(self, guild_id: int, role_id: int):
        """Define o cargo de mediador para um servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mediator_roles (guild_id, role_id)
                    VALUES (%s, %s)
                    ON CONFLICT (guild_id) DO UPDATE SET role_id = %s
                """, (guild_id, role_id, role_id))
                conn.commit()

    def get_mediator_role(self, guild_id: int) -> Optional[int]:
        """Retorna o ID do cargo de mediador configurado para o servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT role_id FROM mediator_roles WHERE guild_id = %s", (guild_id,))
                result = cur.fetchone()
                return result[0] if result else None

    # Métodos de canal de resultados
    def set_results_channel(self, guild_id: int, channel_id: int):
        """Define o canal de resultados para um servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO results_channels (guild_id, channel_id)
                    VALUES (%s, %s)
                    ON CONFLICT (guild_id) DO UPDATE SET channel_id = %s
                """, (guild_id, channel_id, channel_id))
                conn.commit()

    def get_results_channel(self, guild_id: int) -> Optional[int]:
        """Retorna o ID do canal de resultados configurado para o servidor"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT channel_id FROM results_channels WHERE guild_id = %s", (guild_id,))
                result = cur.fetchone()
                return result[0] if result else None

    # Métodos de metadados de fila (PERSISTÊNCIA)
    def save_queue_metadata(self, message_id: int, mode: str, bet_value: float, mediator_fee: float, channel_id: int, currency_type: str = "sonhos"):
        """Salva metadados de uma fila no PostgreSQL"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                queue_id = f"{mode}_{message_id}"
                cur.execute("""
                    INSERT INTO queue_metadata (message_id, queue_id, mode, bet_value, mediator_fee, channel_id, currency_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE SET
                        queue_id = %s,
                        mode = %s,
                        bet_value = %s,
                        mediator_fee = %s,
                        channel_id = %s,
                        currency_type = %s
                """, (message_id, queue_id, mode, bet_value, mediator_fee, channel_id, currency_type,
                      queue_id, mode, bet_value, mediator_fee, channel_id, currency_type))
                conn.commit()
                logger.info(f"✅ Metadados salvos no PostgreSQL: queue_id={queue_id}, bet_value={bet_value}, currency={currency_type}")

    def get_queue_metadata(self, message_id: int) -> Optional[dict]:
        """Retorna metadados de uma fila pelo message_id do PostgreSQL"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT queue_id, mode, bet_value, mediator_fee, channel_id, message_id, currency_type
                    FROM queue_metadata
                    WHERE message_id = %s
                """, (message_id,))
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None

    def get_all_queue_metadata(self) -> dict:
        """Retorna todos os metadados de filas do PostgreSQL"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM queue_metadata")
                results = cur.fetchall()
                return {str(row['message_id']): dict(row) for row in results}

    def delete_queue_metadata(self, message_id: int):
        """Remove metadados de uma fila do PostgreSQL"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM queue_metadata WHERE message_id = %s", (message_id,))
                conn.commit()
                logger.info(f"🗑️ Metadados removidos do PostgreSQL: message_id={message_id}")
