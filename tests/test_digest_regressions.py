from types import SimpleNamespace

from digest import digest_llm_hard_deny, digest_semantic_keys, format_news_entry
from filters import passes_filters
from content_quality import rank_digest_candidates
from news_fingerprint import semantic_news_key
from text_cleaner import clean_text


def _item(title: str, summary: str = ""):
    candidate = SimpleNamespace(
        title=title,
        summary=summary,
        source="test",
        link="https://example.com",
    )
    return SimpleNamespace(candidate=candidate)


def _candidate(title: str, source: str, link: str, summary: str = ""):
    return SimpleNamespace(
        title=title,
        summary=summary,
        source=source,
        link=link,
        published_at=None,
    )


def test_world_cup_player_noise_is_filtered():
    cases = [
        "Fede Valverde's Uruguay eliminated from 2026 World Cup",
        "Spain clinch first place in their group as Marc Cucurella features in win over Uruguay",
        "Courtois Belgica siguen adelante en Mundial: goleada, primeros de grupo",
        "Madrid World Cup Spotlight: Marc Cucurella and Spain scrape past the finish line against Uruguay",
        "El dato con el que Thibaut Courtois entra en la historia de Belgica",
        "Uruguay vuelve a firmar otra dolorosa eliminacion en fase de grupos",
    ]

    for title in cases:
        assert passes_filters(title, source="test") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_basketball_is_filtered_even_when_real_madrid_is_mentioned():
    title = "Juancho Hernangomez, en el radar del Real Madrid"
    headline = "Хуанчо Эрнангомес на радаре Реала"

    assert passes_filters(title, source="test") is False
    assert digest_llm_hard_deny(_item(title), headline) is True


def test_world_cup_transfer_context_can_stay():
    title = (
        "Ramon Mon: si Olise no puede venir al Real Madrid, Florentino Perez "
        "quiere fichar a un jugador que sea gran estrella mundial"
    )
    headline = "Флорентино Перес хочет подписать звезду чемпионата мира вместо Олисе"

    assert passes_filters(title, source="test") is True
    assert digest_llm_hard_deny(_item(title), headline) is False


def test_celebrity_world_cup_noise_is_filtered():
    title = "Actor Channing Tatum attends World Cup match between Norway and France dressed as Erling Haaland"

    assert passes_filters(title, source="test") is False
    assert digest_llm_hard_deny(_item(title), title) is True


def test_evening_digest_national_team_noise_is_filtered():
    cases = [
        "Kylian Mbappe flipped the narrative during France vs Norway",
        "De apellido verdugo del Real Madrid a expulsion contra Espana: la historia de Agustin Canobbio",
        "Bellingham has become Tuchel's most important player",
        "Bonito reencuentro Cristiano Ronaldo y Rodrygo: el portugues se preocupo por su lesion",
        "La familia cule de Cucurella",
        "El reencuentro Cristiano-Rodrygo",
        "Ronaldo Nazario: Mbappe me recuerda a mi prime",
        "8 Real Madrid players still going strong at the World Cup for the round of 32",
        "Возвращение Криштиану и Родриго",
        "Роналду Назарио: «Мбаппе напоминает мне меня в расцвете сил»",
        "Анчелотти отказывается участвовать в японских «интеллектуальных играх»",
        "Роналду «забыл» о Винисиусе: «Я не вижу другого такого, как Неймар, чтобы выиграть матч»",
    ]

    for title in cases:
        assert passes_filters(title, source="test") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_morning_digest_low_signal_items_are_filtered():
    cases = [
        ("Bernardo Silva stays on the bench in Portugal's 0-0 draw with Colombia", "Managing Madrid"),
        ("Rodrygo aparece en Miami y saca la primera foto de equipo con Bernardo Silva", "Marca - Real Madrid"),
        (
            "Dani Carvajal, 34 anos, sobre futbol: jovenes deben disfrutar deporte, ahora con 15 anos "
            "con redes sociales ya quieren ser futbolistas",
            "Defensa Central",
        ),
        (
            "Toni Kroos said what Liverpool and Bayern Munich fans are terrified to confess",
            "The Real Champs",
        ),
        (
            "Micah Richards told it like it is when addressing Trent Alexander-Arnold controversy",
            "The Real Champs",
        ),
        (
            "Brazil manager Carlo Ancelotti refuses to engage in Japan mind games ahead of round 32 clash",
            "ESPN FC",
        ),
        (
            "How new Brazil is taking shape and why Cunha plays a key role",
            "BBC Sport Football",
        ),
        (
            "Ronaldo Nazário: Mbappe me recuerda a mi en mi mejor momento",
            "Marca - Real Madrid",
        ),
        (
            "Antonio Rudiger, 33 anos, futbolista del Real Madrid: mi infancia estuvo marcada por la pobreza",
            "Sport - Real Madrid",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_day_digest_live_low_signal_items_are_filtered():
    cases = [
        ("Image: Real Madrid winger shares first photo with summer signing", "Madrid Universal"),
        (
            "Gary Neville affirmed what Real Madrid fans have been saying for weeks about Trent Alexander-Arnold",
            "The Real Champs",
        ),
        (
            "Gary Neville, exfutbolista, 51 anos: Tuchel no ha querido en Mundial a Alexander-Arnold, "
            "es clase mundial y ha cogido laterales propensos a lesionarse",
            "Defensa Central",
        ),
        ("La bienvenida de Rodrygo a Bernardo Silva", "Mundo Deportivo - Real Madrid"),
        (
            "Laporta contra cuerdas: Barcelona debe este año 123 millones a Goldman Sachs "
            "y necesita pedir 500 mas para pagar el Camp Nou",
            "Defensa Central",
        ),
        ("Bienvenida Rodrygo Bernardo Silva", "Mundo Deportivo - Real Madrid"),
        ("Giro Mundial de Brahim: lider con Marruecos y renovado para Mourinho", "Sport - Real Madrid"),
        (
            "Месси, Мбаппе, Возинья — в символической сборной группового этапа ЧМ-2026 по версии Opta",
            "Чемпионат - Футбол",
        ),
        (
            "El rincon de Madrid en el que Bellingham tiene dos casas: antiguo coto de caza, zonas verdes "
            "y a 10 minutos del Santiago Bernabeu",
            "Defensa Central",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_cross_language_duplicate_semantic_keys():
    assert semantic_news_key("Real Madrid doctor resigns 2026") == semantic_news_key(
        "Dimite Manuel Arroyo, medico del primer equipo del Real Madrid"
    )
    assert semantic_news_key("Real Madrid academy goalkeeper wanted by several La Liga clubs") == semantic_news_key(
        "Equipos de Primera luchan por Fran Gonzalez, meta del Castilla"
    )


def test_rank_digest_groups_cross_language_duplicates():
    candidates = [
        _candidate("Real Madrid doctor resigns 2026", "Managing Madrid", "https://example.com/doctor-en"),
        _candidate(
            "Dimite Manuel Arroyo, medico del primer equipo del Real Madrid",
            "Sport - Real Madrid",
            "https://example.com/doctor-es",
        ),
        _candidate(
            "Real Madrid academy goalkeeper wanted by several La Liga clubs",
            "Madrid Universal",
            "https://example.com/fran-en",
        ),
        _candidate(
            "Equipos de Primera luchan por Fran Gonzalez, meta del Castilla",
            "Mundo Deportivo - Real Madrid",
            "https://example.com/fran-es",
        ),
    ]

    ranked = rank_digest_candidates(candidates, limit=10)

    assert len(ranked) == 2
    assert sorted(len(item.grouped_links) for item in ranked) == [2, 2]


def test_digest_entry_uses_html_link():
    item = _item("Test title")
    item.candidate.source = "Test Source"
    item.candidate.link = "https://example.com/story?x=1&y=2"
    item.related_sources = []

    rendered = format_news_entry(1, item, title_override="Нормальный заголовок")

    assert '<a href="https://example.com/story?x=1&amp;y=2">' in rendered
    assert "](" not in rendered


def test_digest_semantic_key_blocks_later_breaking_variant():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid doctor resigns 2026",
                "Managing Madrid",
                "https://example.com/doctor-digest",
            )
        ],
        limit=10,
    )

    keys = digest_semantic_keys(ranked)

    assert "staff:doctor-resigns:manuel-arroyo" in keys
    assert semantic_news_key(
        "Es oficial, dimite uno de los medicos del Real Madrid tras un ano en el cargo"
    ) in keys


def test_mbappe_role_headline_is_shortened():
    title = (
        "Роль, которую Килиан Мбаппе больше всего хочет получить в мадридском "
        "«Реале», наконец-то может оказаться в пределах досягаемости"
    )

    assert clean_text(title) == "Мбаппе может получить желаемую роль в «Реале»"


def test_morning_digest_translation_glitches_are_cleaned():
    assert clean_text(
        "Хаби Алонсо против подписания суперзвезды Челси Реалом"
    ) == "Хаби Алонсо хочет помешать «Реалу» подписать звезду «Челси»"
    assert clean_text(
        "Хаби Алонсо может насолить Флорентино Пересу с планом по Энцо Фернандесу"
    ) == "Хаби Алонсо может помешать планам Флорентино по Энцо Фернандесу"
    assert clean_text(
        "«Реал» знает, что подписание крупного контракта с полузащитником потребует продажи с тремя звездами на руках"
    ) == "«Реал» понимает: крупный трансфер в центр поля потребует продаж"
    assert clean_text(
        "Клуб Ла Лиги рассматривает возможность перехода защитника мадридского «Реала» на правах аренды"
    ) == "Клуб Ла Лиги рассматривает аренду защитника «Реала»"
    assert clean_text(
        "Реал закладывает основу для Энцо Фернандеса решением по Камавинге"
    ) == "«Реал» готовит почву для Энцо Фернандеса решением по Камавинге"
    assert clean_text(
        "Фабрицио Романо подтверждает, что «Реал» является главным соперником «Жемчужины чемпионата мира»: «Сити» уже ведет переговоры с Буадди о том, чтобы оставить его в аренде на один…"
    ) == "Фабрицио Романо: «Реал» конкурирует с «Сити» за Буадди"
    assert clean_text(
        "Отец Нико Паса подтвердил его продолжение в Комо с одобрением Реала"
    ) == "Отец Нико Паса подтвердил: он останется в «Комо» с одобрения «Реала»"
    assert clean_text(
        "ПСЖ вмешивается в борьбу за игрока, которого хочет Мадрид"
    ) == "ПСЖ вмешался в борьбу за трансферную цель «Реала»"
    assert clean_text(
        "Рампа выхода для двух неприкасаемых: «Реал» нужно продать"
    ) == "У двух недавних неприкасаемых появился шанс на уход: «Реалу» нужны продажи"
    assert clean_text(
        "ПСЖ беспокоится о конце Бундеслиги, которого хочет Мадрид"
    ) == "ПСЖ вмешался в борьбу за вингера из Бундеслиги, которого хочет «Реал»"
    assert clean_text(
        "«Реал» устанавливает цену ухода Камавинга в 60 миллионов"
    ) == "«Реал» оценил возможный уход Камавинги в 60 млн евро"
    assert clean_text(
        "От юного таланта Реала до полупрофессионального уровня: клуб устанавливает цену ухода Камавинги в 60 миллионов"
    ) == "«Реал» оценил возможный уход Камавинги в 60 млн евро"
    assert clean_text(
        "Каприз Каррераса с Моуринью, который превратился в кошмар"
    ) == "Каррерас был желанием Моуринью, но трансфер стал проблемой"
    assert clean_text(
        "Каприз Каррераса с Моуринью превратился в кошмар"
    ) == "Каррерас был желанием Моуринью, но трансфер стал проблемой"
    assert clean_text(
        "Дэвид Орнштейн, журналист: «Ни Премьер-лига, ни» Реал», Ян Диоманде не выберет» ПСЖ», если уйдет после чемпионата мира»"
    ) == "Дэвид Орнштейн: Диоманде выберет ПСЖ, а не «Реал», если уйдёт после чемпионата мира"
    assert clean_text(
        "Флорентино запускает 'глобальную стратегию' для «Реала»"
    ) == "Флорентино запускает «глобальную стратегию» для «Реала»"
    assert clean_text(
        "Мидфилдер Реала станет капитаном клуба"
    ) == "Вальверде станет капитаном «Реала»"
    assert clean_text(
        "«Реал» исполнит желание Винисиуса Жуниора раньше, чем Михаэль Олизе"
    ) == "«Реал» исполнит желание Винисиуса Жуниора раньше, чем Майкл Олисе"
    assert clean_text(
        "Родриги появляется в Майами и делает первое командное с Бернардо Силвой"
    ) == "Родриго появляется в Майами и делает первое командное фото с Бернарду Силвой"
    assert clean_text(
        "Мика Ричардс рассказал все как есть, обращаясь к спору между Трентом Александром и Арнольдом"
    ) == "Мика Ричардс рассказал все как есть, обращаясь к спору между Трентом Александер-Арнольдом"
