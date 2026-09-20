"""
Rate limiting (protection anti-bruteforce réseau, en complément du
verrouillage de compte applicatif — voir services/auth_service.py).

Stockage en mémoire par défaut : suffisant pour un déploiement mono-instance
ou pour le développement. En production multi-instance, configurer un
backend Redis partagé (voir README, section Déploiement) pour que la limite
s'applique correctement derrière un load balancer.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
