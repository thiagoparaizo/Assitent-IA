from typing import List, Dict, Any

# Lista ampliada de categorias para vários setores
DEFAULT_CATEGORIES = [
    # Categorias Genéricas
    {"id": "general", "name": "Geral", "description": "Informações gerais não classificadas em outras categorias"},
    {"id": "faq", "name": "Perguntas Frequentes", "description": "Respostas para perguntas comuns dos clientes"},
    {"id": "policies", "name": "Políticas e Termos", "description": "Políticas, termos e condições da empresa"},
    
    # Saúde
    {"id": "healthcare", "name": "Saúde", "description": "Informações gerais sobre saúde"},
    {"id": "medical_procedures", "name": "Procedimentos Médicos", "description": "Detalhes sobre procedimentos médicos"},
    {"id": "dental", "name": "Odontologia", "description": "Informações relacionadas a tratamentos dentários"},
    {"id": "pharmacy", "name": "Farmácia", "description": "Medicamentos e produtos farmacêuticos"},
    {"id": "nutrition", "name": "Nutrição", "description": "Orientações nutricionais e dietas"},
    
    # Finanças
    {"id": "finance", "name": "Finanças", "description": "Tópicos gerais de finanças e contabilidade"},
    {"id": "banking", "name": "Bancário", "description": "Serviços bancários e financeiros"},
    {"id": "investments", "name": "Investimentos", "description": "Informações sobre produtos de investimento"},
    {"id": "taxes", "name": "Impostos", "description": "Questões fiscais e tributárias"},
    {"id": "insurance", "name": "Seguros", "description": "Informações sobre seguros e coberturas"},
    
    # Comércio
    {"id": "retail", "name": "Varejo", "description": "Informações gerais para comércio varejista"},
    {"id": "products", "name": "Produtos", "description": "Catálogo e especificações de produtos"},
    {"id": "pricing", "name": "Preços", "description": "Informações sobre preços e promoções"},
    {"id": "shipping", "name": "Envio e Entrega", "description": "Políticas e informações de envio"},
    {"id": "returns", "name": "Trocas e Devoluções", "description": "Políticas de devolução e troca"},
    
    # Tecnologia
    {"id": "technology", "name": "Tecnologia", "description": "Informações gerais sobre tecnologia"},
    {"id": "software", "name": "Software", "description": "Informações sobre software e aplicativos"},
    {"id": "hardware", "name": "Hardware", "description": "Informações sobre equipamentos e hardware"},
    {"id": "it_support", "name": "Suporte TI", "description": "Suporte técnico e resolução de problemas"},
    {"id": "security", "name": "Segurança", "description": "Segurança digital e proteção de dados"},
    
    # Educação
    {"id": "education", "name": "Educação", "description": "Tópicos educacionais gerais"},
    {"id": "courses", "name": "Cursos", "description": "Informações sobre cursos e treinamentos"},
    {"id": "academic", "name": "Acadêmico", "description": "Conteúdo acadêmico e de pesquisa"},
    {"id": "tutorials", "name": "Tutoriais", "description": "Guias passo a passo e instruções"},
    
    # Serviços
    {"id": "services", "name": "Serviços", "description": "Informações sobre serviços oferecidos"},
    {"id": "scheduling", "name": "Agendamento", "description": "Informações sobre marcação e agendamento"},
    {"id": "appointments", "name": "Consultas", "description": "Detalhes sobre consultas e atendimentos"},
    {"id": "support", "name": "Atendimento", "description": "Suporte ao cliente e atendimento"},
    
    # Jurídico
    {"id": "legal", "name": "Jurídico", "description": "Informações jurídicas gerais"},
    {"id": "contracts", "name": "Contratos", "description": "Informações sobre contratos e acordos"},
    {"id": "compliance", "name": "Compliance", "description": "Normas e conformidade regulatória"},
    
    # Recursos Humanos
    {"id": "hr", "name": "RH", "description": "Recursos Humanos e gestão de pessoal"},
    {"id": "benefits", "name": "Benefícios", "description": "Benefícios para funcionários"},
    {"id": "recruitment", "name": "Recrutamento", "description": "Processos de contratação"},
    {"id": "training", "name": "Treinamento", "description": "Materiais de capacitação e desenvolvimento"},
    
    # Setores Específicos
    {"id": "real_estate", "name": "Imobiliário", "description": "Setor imobiliário e propriedades"},
    {"id": "tourism", "name": "Turismo", "description": "Informações turísticas e viagens"},
    {"id": "hospitality", "name": "Hotelaria", "description": "Serviços de hospedagem e hotelaria"},
    {"id": "automotive", "name": "Automotivo", "description": "Setor automotivo e veículos"},
    {"id": "energy", "name": "Energia", "description": "Setor energético e utilities"},
    {"id": "logistics", "name": "Logística", "description": "Logística e transporte"},
    {"id": "agriculture", "name": "Agricultura", "description": "Setor agrícola e agronegócio"},
    {"id": "construction", "name": "Construção", "description": "Construção civil e arquitetura"},
    {"id": "manufacturing", "name": "Indústria", "description": "Processos industriais e manufatura"},
    
    # Conteúdo Específico
    {"id": "technical", "name": "Técnico", "description": "Documentação técnica e especificações"},
    {"id": "onboarding", "name": "Onboarding", "description": "Material de integração de clientes/funcionários"},
    {"id": "marketing", "name": "Marketing", "description": "Material de marketing e comunicação"},
    {"id": "internal", "name": "Interno", "description": "Documentação de uso interno"},
]

# Função para obter categorias por ID
def get_category_by_id(category_id: str) -> Dict[str, Any]:
    for category in DEFAULT_CATEGORIES:
        if category["id"] == category_id:
            return category
    return {"id": category_id, "name": category_id.capitalize(), "description": "Categoria"}

# Função para transformar lista de categorias em mapa para busca rápida
def get_categories_map() -> Dict[str, Dict[str, Any]]:
    return {category["id"]: category for category in DEFAULT_CATEGORIES}