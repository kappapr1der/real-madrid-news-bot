from types import SimpleNamespace

from digest import digest_llm_hard_deny, digest_render_plan, digest_semantic_keys, format_news_entry
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
        "What Thomas Tuchel did to Trent Alexander-Arnold feels like a fireable offense",
        "Icons Luka Modric and Cristiano Ronaldo hope to avoid World Cup elimination",
        "Croatia Portugal Luka Modric Cristiano Ronaldo 2026 World Cup",
        "«Иконы» Модрич и Роналду надеются избежать удаления с чемпионата Мира",
        "Bonito reencuentro Cristiano Ronaldo y Rodrygo: el portugues se preocupo por su lesion",
        "La familia cule de Cucurella",
        "El reencuentro Cristiano-Rodrygo",
        "Ronaldo Nazario: Mbappe me recuerda a mi prime",
        "8 Real Madrid players still going strong at the World Cup for the round of 32",
        "Возвращение Криштиану и Родриго",
        "Cristiano Ronaldo delivers a clear message to the football world",
        "Роналду Назарио: «Мбаппе напоминает мне меня в расцвете сил»",
        "Анчелотти отказывается участвовать в японских «интеллектуальных играх»",
        "Роналду «забыл» о Винисиусе: «Я не вижу другого такого, как Неймар, чтобы выиграть матч»",
    ]

    for title in cases:
        assert passes_filters(title, source="test") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_modric_career_decision_noise_is_filtered():
    cases = [
        (
            "Luka Modric faces major career decision after World Cup exit as Real Madrid monitor situation",
            "Madrid Universal",
        ),
        (
            "Real Madrid atento a la decision de Modric",
            "Mundo Deportivo - Real Madrid",
        ),
        (
            "Луке Модричу предстоит принять важное карьерное решение после вылета с чемпионата мира, а «Реал» следит за ситуацией",
            "Madrid Universal",
        ),
        (
            "Модрич должен принять решение: «Реал» в бегах",
            "Mundo Deportivo - Real Madrid",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_vague_bernabeu_transfer_clickbait_is_filtered():
    title = "El Real Madrid ya no cree en el fichaje de este jugador"
    headline = "«Реал» больше не верит в трансфер этого игрока"

    assert passes_filters(title, source="Bernabéu Digital") is False
    assert digest_llm_hard_deny(_item(title), headline) is True


def test_preflight_noise_from_social_and_national_team_items_is_filtered():
    cases = [
        (
            "Cucurella responde a la queja de Courtois por no seguirle en Instagram: "
            "el nuevo defensa del Madrid tardó 10 horas en hacerlo",
            "Defensa Central",
        ),
        (
            "Man United legends question Tuchel’s decision to omit Real Madrid superstar: "
            "‘A head scratcher’",
            "Madrid Universal",
        ),
        ("Dardo de Courtois a Cucurella", "Mundo Deportivo – Real Madrid"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
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
        (
            "Fede Valverde accepts responsibility after Uruguay's World Cup exit: I know I wasn't up to it",
            "Managing Madrid",
        ),
        (
            "A Bernardo Silva no le sienta bien el Mundial",
            "Mundo Deportivo - Real Madrid",
        ),
        (
            "Появились подробности по травме Джона Кордобы и его шансах сыграть на ЧМ",
            "Чемпионат - Футбол",
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
        (
            "France Morocco live stream score result World Cup quarter final: Michael Olise appeal rejected by FIFA after Atlas Lions tackle",
            "Independent Football",
        ),
        (
            "Fichajes Real Madrid: ultimas noticias",
            "Marca - Real Madrid",
        ),
        (
            "Cuando juegan los jugadores del Real Madrid en cuartos del Mundial",
            "Mundo Deportivo - Real Madrid",
        ),
        (
            "Siro Lopez, periodista: me he encontrado en Estados Unidos con una estrella Real Madrid y he hablado sobre su nueva vida en Espana con Bernardo Silva",
            "Defensa Central",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_day_digest_latest_low_signal_items_are_filtered():
    cases = [
        (
            "Manolo Lama, 64 anos, periodista: la lesion Raphinha ha venido bien a Vinicius, "
            "no a Brasil, ahora se siente superestrella y todos van a jugar para el",
            "Defensa Central",
        ),
        (
            "Hora y cuando juegan los madridistas en el Mundial",
            "Mundo Deportivo - Real Madrid",
        ),
        (
            "Reranking Europe's top clubs by player performance at the World Cup: Bayern, Real Madrid, Liverpool",
            "ESPN FC",
        ),
        (
            "An incredible man: how Carlo Ancelotti has turned Brazil into potential World Cup winner",
            "Guardian Football",
        ),
        (
            "Cucurella vuela en el Mundial... y en el Madrid se frotan las manos",
            "Marca - Real Madrid",
        ),
        (
            "El Real Madrid, protagonista en la tanda de penaltis del Australia-Egipto",
            "Mundo Deportivo - Real Madrid",
        ),
        (
            "Bellingham (23 anos), sobre lo que mas le gusta de Espana: Para caminar por una gran ciudad",
            "Defensa Central",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_july_absence_noise_items_are_filtered():
    cases = [
        ("Jaime Pradilla jugador del Real Madrid", "Bernabeu Digital"),
        ("Прямая трансляция матча Парагвай - Франция: Мбаппе вывел «Синие» в четвертьфинал", "Independent Football"),
        ("Парагвай не сломил Мбаппе, даже отрезав от мяча. Репортаж Романцова", "Sports.ru"),
        ("Как Анчелотти переворачивает матчи ЧМ", "Sports.ru"),
        ("Секретная лаборатория Анчелотти: поиск пути к Гекса", "Marca - Real Madrid"),
        ("Рынок трансферов сегодня, 6 июля, в прямом эфире | Последние новости о переходах Реала Мадрид", "Marca - Real Madrid"),
        ("Бывший игрок «Мадрида» выпотрошил Анчелотти после поражения от Бразилии", "Marca - Real Madrid"),
        ("Уже сейчас до боли очевидно, что Винисиус проходит курс лечения у Неймара", "The Real Champs"),
        ("Сборная Испании в составе Марка Кукуреллы обыграла Португалию на победной 90-й минуте", "Managing Madrid"),
        ("Криштиану Роналду рассказал о своем португальском наследии без всякой лжи", "The Real Champs"),
        ("«Ни капли осуждения». Генич отреагировал на трансфер Сперцяна в «Аль-Ахли»", "Чемпионат - Футбол"),
        ("Бывший житель Мадрида: «Люди ели очень мало; мы, дети, ели спагетти с помидорами»", "Mundo Deportivo - Real Madrid"),
        ("Гарет Бэйл (36 лет), бывший футболист: «Я играл за Луку Модрича 13 лет»", "Defensa Central"),
        ("«Колонизированный камерунец». Парагвай ненавидит Мбаппе", "Sports.ru"),
        ("Тени Кина и Джеррарда на показе в Беллингеме - Руни", "BBC Sport Football"),
        ("Марк Кукурелла отразил всех болельщиков мадридского «Реала» после поражения Криштиану Роналду", "The Real Champs"),
        ("«Реал» будет иметь минимум одного игрока в финале чемпионата мира", "Defensa Central"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_july_ninth_clickbait_is_filtered():
    title = "Jose Mourinho just made a Real Madrid transfer decision nobody saw coming"
    headline = "Моуринью принял неожиданное трансферное решение в «Реале»"

    assert passes_filters(title, source="The Real Champs") is False
    assert digest_llm_hard_deny(_item(title), headline) is True


def test_evening_digest_july_ninth_noise_is_filtered():
    cases = [
        (
            "Хаби Алонсо рассказал, почему он решил возглавить Челси",
            "Чемпионат - Футбол",
        ),
        (
            "Atletico pesca talento Fabrica Alvaro Vega refuerza juvenil",
            "Marca - Real Madrid",
        ),
        (
            "Атлетико ловит талантливых игроков на Заводе: Альваро Вега усиливает молодежный состав",
            "Marca - Real Madrid",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_morning_digest_july_tenth_noise_is_filtered():
    cases = [
        (
            "Nueva etapa! Asi luce Xabi Alonso en su primer entrenamiento con el Chelsea",
            "Marca - Real Madrid",
        ),
        (
            "Tope del Real Madrid con Vini, cambios de plan con Mourinho y decision clave en los fichajes",
            "Bernabeu Digital",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True

    roundup = _item("Editorial roundup")
    roundup.candidate.link = (
        "https://www.bernabeudigital.com/noticias/"
        "tope-real-madrid-vini-cambios-plan-mourinho-decision-clave-fichajes-344279"
    )
    assert digest_llm_hard_deny(roundup) is True


def test_morning_digest_july_tenth_titles_are_cleaned():
    assert clean_text(
        "Килиан Мбаппе сообщил об обновлении по травме"
    ) == "Мбаппе рассказал о состоянии после травмы"
    assert clean_text(
        "Тчуамени получит на 10 миллионов больше, но всё равно будет уступать англичанам в Мадриде"
    ) == "Тчуамени после продления будет получать 10 млн евро в год"
    assert clean_text(
        "Моуринью и его новый штаб «Реал» берут на себя управление в Вальдебебас"
    ) == "Моуринью и его штаб приступили к работе в Вальдебебасе"


def test_day_digest_july_tenth_noise_is_filtered():
    cases = [
        ("Jude Bellingham has ended a World Cup debate that should've never even existed", "The Real Champs"),
        ("Jurgen Klopp, Kylian Mbappe and Liverpool talks on private jet PSG transfer", "ESPN FC"),
        ("Какие рекорды уже побил ЧМ-2026: здесь не только Месси, Роналду и Очоа", "Sports.ru"),
        ("Real Madrid presume cantera Espana Europeo sub-19", "Bernabeu Digital"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_mourinho_valdebebas_start_uses_one_semantic_key():
    breaking_title = "Confirmado: Jose Mourinho ya se ha puesto a trabajar en Valdebebas"
    digest_title = "IMAGES: Mourinho and his new Real Madrid staff take charge at Valdebebas"

    assert semantic_news_key(breaking_title) == "staff:mourinho-starts-at-valdebebas"
    assert semantic_news_key(digest_title) == "staff:mourinho-starts-at-valdebebas"


def test_evening_digest_personal_former_player_noise_is_filtered():
    cases = [
        ("Fallece el padre de Ricardo Carvalho", "Marca - Real Madrid"),
        ("Скончался отец Рикарду Карвалью", "Marca - Real Madrid"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_evening_digest_clickbait_and_lifestyle_noise_is_filtered():
    cases = [
        ("Does Carlo Ancelotti hate Endrick? Is it really a thing?", "FourFourTwo"),
        ("Divertido momento entre Marcelo y Linda Caicedo", "Mundo Deportivo - Real Madrid"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_recovered_digest_noise_from_july_first_is_filtered():
    cases = [
        ("Real Madrid queda fuera del acuerdo de inversion del grupo Pau Gasol en Liga F", "Marca - Real Madrid"),
        ("Chelsea signs Italian defender Palestra for 47 million pounds", "BBC Sport Football"),
        ("Juanma Rodriguez sin filtros sobre Mbappe en Francia", "Sport - Real Madrid"),
        (
            "Toni Kroos got brutally honest about how Florian Wirtz and Jamal Musiala stack up with Jude Bellingham",
            "The Real Champs",
        ),
        ("David Alaba claro: jugar en Espana es especial para mi", "Marca - Real Madrid"),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_evening_july_first_low_signal_items_are_filtered():
    cases = [
        ("4 Champions eclipsan eliminatoria seleccion jugador", "Bernabeu Digital"),
        ("So much for the Endrick breakout under Carlo Ancelotti", "The Real Champs"),
        ("Real Madrid C puede mantener plaza en Segunda RFEF pese a haber descendido", "Mundo Deportivo - Real Madrid"),
        (
            "George Weah said what Real Madrid fans have been whispering about Kylian Mbappe and Lamine Yamal",
            "The Real Champs",
        ),
    ]

    for title, source in cases:
        assert passes_filters(title, source=source) is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_barcelona_julian_alvarez_rival_noise_is_filtered():
    cases = [
        "Barca copia al Real Madrid desesperada por firmar a Julian Alvarez",
        "Barcelona copies Real Madrid in desperate attempt to sign Julian Alvarez",
        "«Барселона» копирует «Реал», отчаянно пытаясь подписать Хулиана Маньяра Альвареса",
    ]

    for title in cases:
        assert passes_filters(title, source="Bernabeu Digital") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_preflight_low_signal_items_are_filtered():
    cases = [
        "«Я его съем». Ямаль — о противостоянии с Кукурельей в Ла Лиге",
        (
            "El rincón donde desconecta Luka Modric en Madrid tiene 54 años y está a 7 minutos "
            "del estadio Santiago Bernabéu: Es ideal para comer carne a la brasa"
        ),
    ]

    for title in cases:
        assert passes_filters(title, source="test") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_cross_language_duplicate_semantic_keys():
    assert semantic_news_key("Real Madrid doctor resigns 2026") == semantic_news_key(
        "Dimite Manuel Arroyo, medico del primer equipo del Real Madrid"
    )
    assert semantic_news_key(
        "Oficial: Nico Paz queda otra temporada en Como"
    ) == semantic_news_key(
        "Oficial: Nico Paz deja el Real Madrid y pasa al Como"
    )
    assert semantic_news_key("Oficial: Nico Paz queda otra temporada en Como") == "transfer:nico-paz-como"
    assert semantic_news_key(
        "Joan Laporta takes aim at Florentino Perez and Real Madrid"
    ) == semantic_news_key(
        "Laporta attacks Real Madrid quotes 2026"
    )
    assert semantic_news_key(
        "Barcelona president hits back at Real Madrid over complaint to UEFA"
    ) == semantic_news_key(
        "Laporta dispara al Real Madrid"
    )
    assert semantic_news_key("Laporta attacks Real Madrid quotes 2026") == "barca:laporta-attacks-real"
    assert semantic_news_key("Real Madrid academy goalkeeper wanted by several La Liga clubs") == semantic_news_key(
        "Equipos de Primera luchan por Fran Gonzalez, meta del Castilla"
    )
    assert semantic_news_key(
        "Confirmed: Real Madrid donate EUR1 million to support those affected by Venezuela earthquakes"
    ) == semantic_news_key(
        "Madrid lanza campana solidaria con Venezuela, club y Florentino donan un millon de euros"
    )
    assert semantic_news_key(
        "Valencia want to take Joan Martinez on loan"
    ) == semantic_news_key(
        "Valencia pregunta por Joan Martinez"
    )
    assert semantic_news_key(
        "Real Madrid again skip key La Liga and RFEF meeting"
    ) == semantic_news_key(
        "Real Madrid no acudira a la reunion de todos los clubes en la sede de LaLiga"
    )
    assert semantic_news_key(
        "Michael Olise to hold talks with Bayern while Real Madrid continue to monitor situation"
    ) == semantic_news_key(
        "Real Madrid and Galactico set for important talks with Bayern Munich amid future speculation"
    )
    assert semantic_news_key(
        "Herbert Hainer, presidente del Bayern, tajante con el Real Madrid: pueden ahorrarse el esfuerzo"
    ) == semantic_news_key(
        "Olise solicita una reunion con el Bayern"
    )
    assert semantic_news_key(
        "Real Madrid offer 23-year-old midfielder to Manchester City"
    ) == semantic_news_key(
        "Real Madrid and Manchester City discuss Camavinga deal"
    )
    assert semantic_news_key(
        "Real Madrid offer Camavinga a top Premier League option"
    ) == semantic_news_key(
        "Madrid ofrece a Camavinga al City"
    )
    assert semantic_news_key(
        "Real Madrid offer 23-year-old midfielder to Manchester City"
    ) == "transfer:camavinga-manchester-city"
    assert semantic_news_key(
        "Fede Valverde: firme en el Real Madrid"
    ) == semantic_news_key(
        "El destino de Fede Valverde en el Real Madrid esta confirmado"
    )
    assert semantic_news_key(
        "Будущее Феде Вальверде в «Реале» подтверждено"
    ) == "player:valverde-stays-real-madrid"
    assert semantic_news_key(
        "Real Madrid do not plan to sign Enzo Fernandez"
    ) == semantic_news_key(
        "Oficial: Real Madrid desmiente estar negociando con Enzo Fernandez"
    )
    assert semantic_news_key(
        "De Neymar a Enzo Fernandez: el Madrid ha emitido 5 comunicados oficiales en su historia anunciando que no estaba negociando con los jugadores"
    ) == "transfer:no-sign:enzo-fernandez"
    assert semantic_news_key(
        "Enzo Fernandez just got hit with the most brutal Real Madrid reality check imaginable"
    ) == "transfer:no-sign:enzo-fernandez"
    assert semantic_news_key(
        "«Реал» не планирует подписывать Энцо Фернандеса"
    ) == "transfer:no-sign:enzo-fernandez"
    assert semantic_news_key(
        "Confirmed: Real Madrid donate EUR1 million to support those affected by Venezuela earthquakes"
    ) == "club:donation:venezuela-earthquake"
    assert semantic_news_key("Valencia want to take Joan Martinez on loan") == "transfer:loan:joan-martinez-valencia"
    assert semantic_news_key("Real Madrid again skip key La Liga and RFEF meeting") == "club:laliga-rfef-meeting-skip"
    assert semantic_news_key("Michael Olise to hold talks with Bayern while Real Madrid monitor situation") == "transfer:olise-bayern-talks-real-monitoring"
    assert semantic_news_key(
        "Tribunal rechaza peticion del Real Madrid para suspender protocolo frente acoso sexual de LaLiga"
    ) == "legal:laliga-harassment-protocol"
    assert semantic_news_key("Otro reves judicial para el Real Madrid por el protocolo de acoso sexual de LaLiga") == "legal:laliga-harassment-protocol"
    assert semantic_news_key(
        "Real Madrid, Vinicius will meet after FIFA World Cup to discuss contract negotiations"
    ) == semantic_news_key(
        "Acercamiento definitivo del Real Madrid y Vini para renovar"
    )
    assert semantic_news_key(
        "60 millones para cerrar la renovacion de la defensa y cerrar la renovacion de Vini Jr"
    ) == "contract:vinicius-renewal"
    assert semantic_news_key(
        "Real Madrid set for EUR12.5 million windfall from former defender's transfer"
    ) != "transfer:rumour:rodri"
    assert semantic_news_key(
        "Mario Gila le deja al Real Madrid una buena cantidad de millones"
    ) == semantic_news_key(
        "La Fabrica que financia al Real Madrid con 600 millones"
    )
    assert semantic_news_key(
        "Ruben Martin sobre las ventas del Madrid: Florentino va a recaudar mas de 200 millones"
    ) == "finance:player-sales-revenue"
    assert semantic_news_key(
        "Real Madrid's La Liga opener against Real Sociedad set to be postponed"
    ) == semantic_news_key(
        "Primer partido Liga Real Madrid aplazado por el Mundial"
    )
    assert semantic_news_key(
        "Confirmado: se atrasa debut Real Madrid en Liga en Bernabeu"
    ) == "schedule:laliga-opener-postponed"
    assert semantic_news_key(
        "Alvaro Arbeloa oficialmente entrenador del Fulham"
    ) == semantic_news_key(
        "Es oficial: Arbeloa nuevo entrenador Fulham firma hasta 2029"
    )
    assert semantic_news_key("Alvaro Arbeloa oficialmente entrenador del Fulham") == "staff:arbeloa-fulham-manager"
    assert semantic_news_key(
        "Oficial: Fran Garcia marcha al Betis"
    ) == semantic_news_key(
        "Es oficial: Madrid anuncia traspaso Fran Garcia Betis"
    )
    assert semantic_news_key("Oficial: Fran Garcia marcha al Betis") == "transfer:fran-garcia-betis"
    assert semantic_news_key(
        "Padre Haaland deja claro que quiere jugar en Madrid"
    ) == semantic_news_key(
        "Clan Haaland vincula Real Madrid novedades blancos"
    )
    assert semantic_news_key("Bombazo Haaland: es probable que juegue en Real Madrid") == "transfer:haaland-family-real-links"
    assert semantic_news_key(
        "Real Madrid to host under-20 Intercontinental Cup final at the Bernabeu"
    ) == semantic_news_key(
        "Real Madrid y Santiago Wanderers lucharan Intercontinental sub-20"
    )
    assert semantic_news_key(
        "Fijan fecha limite para que Real Madrid mueva ficha por Bastoni"
    ) == semantic_news_key(
        "Bloqueo salida Asencio ofertas insuficientes Bastoni"
    )
    assert semantic_news_key(
        "Real Madrid reach agreement to extend midfield mainstay contract until 2031 amid Manchester United interest"
    ) == semantic_news_key(
        "Tchouameni Real Madrid contract extension 2026"
    )
    assert semantic_news_key("Tchouameni signs Real Madrid contract extension until 2031") == "contract:tchouameni-extension"
    assert semantic_news_key(
        "Confirmed: Real Madrid face Deportivo La Coruna in Teresa Herrera Trophy in pre-season"
    ) == semantic_news_key(
        "Es oficial: Real Madrid Mourinho debuta en amistoso contra Deportivo en Trofeo Teresa Herrera"
    )
    assert semantic_news_key(
        "Confirmed: Real Madrid face Deportivo La Coruna in Teresa Herrera Trophy in pre-season"
    ) == "schedule:teresa-herrera-deportivo-friendly"
    assert semantic_news_key(
        "Real Madrid conoce que ganaria ano Fran Garcia"
    ) == semantic_news_key(
        "Asi despedido vestuario Real Madrid Fran Garcia"
    )
    assert semantic_news_key(
        "Real Madrid conoce que ganaria ano Fran Garcia"
    ) == "transfer:fran-garcia-betis"
    assert semantic_news_key(
        "Real Madrid make sweeping medical staff changes following injury-plagued season"
    ) == semantic_news_key(
        "Реал перестраивает медицинский штаб после сезона травм и инцидента с Мбаппе"
    )
    assert semantic_news_key(
        "Real perestraivaet medicinskij shtab posle sezona travm i incidenta s Mbappe"
    ) == "staff:medical-overhaul-after-injuries"


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


def test_rank_digest_groups_daily_contract_and_revenue_threads():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid, Vinicius will meet after FIFA World Cup to discuss contract negotiations",
                "Managing Madrid",
                "https://example.com/vini-contract-en",
            ),
            _candidate(
                "Acercamiento definitivo del Real Madrid y Vini para renovar",
                "Bernabeu Digital",
                "https://example.com/vini-contract-es",
            ),
            _candidate(
                "Mario Gila le deja al Real Madrid una buena cantidad de millones",
                "Mundo Deportivo - Real Madrid",
                "https://example.com/gila-money",
            ),
            _candidate(
                "La Fabrica que financia al Real Madrid con 600 millones",
                "Sport - Real Madrid",
                "https://example.com/fabrica-money",
            ),
            _candidate(
                "Ruben Martin sobre las ventas del Madrid: Florentino va a recaudar mas de 200 millones",
                "Defensa Central",
                "https://example.com/sales-money",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 2
    assert sorted(len(item.grouped_links) for item in ranked) == [2, 3]


def test_rank_digest_groups_july_absence_duplicate_threads():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid's La Liga opener against Real Sociedad set to be postponed",
                "Madrid Universal",
                "https://example.com/laliga-opener-en",
            ),
            _candidate(
                "Confirmado: se atrasa debut Real Madrid en Liga en Bernabeu",
                "Defensa Central",
                "https://example.com/laliga-opener-es",
            ),
            _candidate(
                "Padre Haaland deja claro que quiere jugar en Madrid",
                "Mundo Deportivo - Real Madrid",
                "https://example.com/haaland-father",
            ),
            _candidate(
                "Clan Haaland vincula Real Madrid novedades blancos",
                "Bernabeu Digital",
                "https://example.com/haaland-clan",
            ),
            _candidate(
                "Real Madrid to host under-20 Intercontinental Cup final at the Bernabeu",
                "Madrid Universal",
                "https://example.com/u20-final-en",
            ),
            _candidate(
                "Real Madrid y Santiago Wanderers lucharan Intercontinental sub-20",
                "Marca - Real Madrid",
                "https://example.com/u20-final-es",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 3
    assert sorted(len(item.grouped_links) for item in ranked) == [2, 2, 2]


def test_rank_digest_groups_tchouameni_extension_thread():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid reach agreement to extend midfield mainstay contract until 2031 amid Manchester United interest",
                "Madrid Universal",
                "https://example.com/tchouameni-extension-en",
            ),
            _candidate(
                "Tchouameni Real Madrid contract extension 2026",
                "Managing Madrid",
                "https://example.com/tchouameni-extension-mm",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 1
    assert len(ranked[0].grouped_links) == 2


def test_rank_digest_groups_medical_staff_overhaul_thread():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid make sweeping medical staff changes following injury-plagued season",
                "Madrid Universal",
                "https://example.com/medical-staff-en",
            ),
            _candidate(
                "Реал перестраивает медицинский штаб после сезона травм и инцидента с Мбаппе",
                "Чемпионат - Футбол",
                "https://example.com/medical-staff-ru",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 1
    assert len(ranked[0].grouped_links) == 2


def test_rank_digest_groups_fran_garcia_departure_followups():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid conoce que ganaria ano Fran Garcia",
                "Bernabeu Digital",
                "https://example.com/fran-money",
            ),
            _candidate(
                "Asi despedido vestuario Real Madrid Fran Garcia",
                "Mundo Deportivo - Real Madrid",
                "https://example.com/fran-farewell",
            ),
            _candidate(
                "Oficial: Fran Garcia marcha al Betis",
                "Sport - Real Madrid",
                "https://example.com/fran-betis",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 1
    assert len(ranked[0].grouped_links) == 3


def test_rank_digest_does_not_fill_deferred_sources():
    ranked = rank_digest_candidates(
        [
            _candidate("Real Madrid confirm Courtois injury diagnosis", "Madrid Universal", "https://example.com/one"),
            _candidate("Real Madrid prepare Vinicius renewal talks", "Madrid Universal", "https://example.com/two"),
            _candidate("Real Madrid study Enzo Fernandez transfer", "Madrid Universal", "https://example.com/three"),
            _candidate("Real Madrid name squad for Bayern match", "Madrid Universal", "https://example.com/four"),
        ],
        limit=4,
    )

    assert len(ranked) == 2


def test_digest_render_plan_uses_short_format_for_thin_digest():
    render_format, templates, intro_lines = digest_render_plan("дневного", 4)

    assert render_format == "short"
    assert any("Корот" in template for template in templates)
    assert intro_lines
    assert not any("добивк" in line or "наполнител" in line or "тонк" in line for line in intro_lines)


def test_evening_short_digest_avoids_meta_copy():
    render_format, templates, intro_lines = digest_render_plan("вечернего", 4)

    assert render_format == "short"
    assert not any("Корот" in template or "формат" in template for template in templates)
    assert not any("формат" in line or "пункт" in line for line in intro_lines)


def test_digest_render_plan_uses_full_format_for_normal_digest():
    render_format, templates, intro_lines = digest_render_plan("дневного", 6)

    assert render_format == "full"
    assert any("Дневная" in template or "К этому часу" in template for template in templates)
    assert intro_lines


def test_rank_digest_groups_latest_live_duplicates():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Valencia quiere a Joan Martinez cedido",
                "Managing Madrid",
                "https://example.com/joan-loan",
            ),
            _candidate(
                "Valencia pregunta por Joan Martinez",
                "Marca - Real Madrid",
                "https://example.com/joan-interest",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 1
    assert len(ranked[0].grouped_links) == 2


def test_rank_digest_groups_evening_live_duplicates():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Real Madrid again skip key La Liga and RFEF meeting",
                "Madrid Universal",
                "https://example.com/laliga-rfef",
            ),
            _candidate(
                "Real Madrid no acudira a la reunion de todos los clubes en la sede de LaLiga",
                "Marca - Real Madrid",
                "https://example.com/laliga-meeting",
            ),
            _candidate(
                "Michael Olise to hold talks with Bayern while Real Madrid continue to monitor situation",
                "Managing Madrid",
                "https://example.com/olise-talks",
            ),
            _candidate(
                "Real Madrid and Galactico set for important talks with Bayern Munich amid future speculation",
                "Madrid Universal",
                "https://example.com/olise-bayern",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 2
    assert sorted(len(item.grouped_links) for item in ranked) == [2, 2]


def test_rank_digest_groups_olise_bayern_hainer_duplicate():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Herbert Hainer, presidente del Bayern, tajante con el Real Madrid: pueden ahorrarse el esfuerzo",
                "Bernabeu Digital",
                "https://example.com/hainer-olise",
            ),
            _candidate(
                "Olise solicita una reunion con el Bayern",
                "Sport - Real Madrid",
                "https://example.com/olise-meeting",
            ),
        ],
        limit=10,
    )

    assert len(ranked) == 1
    assert len(ranked[0].grouped_links) == 2


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


def test_digest_semantic_key_blocks_valverde_breaking_variant():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Fede Valverde: firme en el Real Madrid",
                "Marca - Real Madrid",
                "https://example.com/valverde-digest",
            )
        ],
        limit=10,
    )

    keys = digest_semantic_keys(ranked)

    assert "player:valverde-stays-real-madrid" in keys
    assert semantic_news_key("El destino de Fede Valverde en el Real Madrid esta confirmado") in keys


def test_digest_semantic_key_blocks_july_breaking_variants():
    ranked = rank_digest_candidates(
        [
            _candidate(
                "Alvaro Arbeloa oficialmente entrenador del Fulham",
                "Bernabeu Digital",
                "https://example.com/arbeloa-fulham",
            ),
            _candidate(
                "Oficial: Fran Garcia marcha al Betis",
                "Sport - Real Madrid",
                "https://example.com/fran-betis",
            ),
            _candidate(
                "Es oficial: Real Madrid Mourinho debuta en amistoso contra Deportivo en Trofeo Teresa Herrera",
                "Defensa Central",
                "https://example.com/teresa-herrera-deportivo",
            ),
        ],
        limit=10,
    )

    keys = digest_semantic_keys(ranked)

    assert "staff:arbeloa-fulham-manager" in keys
    assert semantic_news_key("Es oficial: Arbeloa nuevo entrenador Fulham firma hasta 2029") in keys
    assert "transfer:fran-garcia-betis" in keys
    assert semantic_news_key("Es oficial: Madrid anuncia traspaso Fran Garcia Betis") in keys
    assert "schedule:teresa-herrera-deportivo-friendly" in keys
    assert semantic_news_key("Confirmed: Real Madrid face Deportivo La Coruna in Teresa Herrera Trophy in pre-season") in keys


def test_mbappe_role_headline_is_shortened():
    title = (
        "Роль, которую Килиан Мбаппе больше всего хочет получить в мадридском "
        "«Реале», наконец-то может оказаться в пределах досягаемости"
    )

    assert clean_text(title) == "Мбаппе может получить желаемую роль в «Реале»"


def test_morning_digest_translation_glitches_are_cleaned():
    assert clean_text(
        "«Реал» сыграет с Депортиво Ла Корунья в рамках турнира Teresa Herrera Trophy в предсезонке"
    ) == "«Реал» сыграет с «Депортиво» в предсезонном Трофее Тересы Эрреры"
    assert clean_text(
        "«Реал» дебютирует под руководством Моуринью в товарищеском матче против Депортиво"
    ) == "Дебют Моуринью состоится в товарищеском матче с «Депортиво»"
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
        "Реал восстановит 90 миллионов, потраченных на трансферы"
    ) == "«Реал» может вернуть 90 млн евро, вложенные в трансферы"
    assert clean_text(
        "Реал открыт к аренде Рауля Асенсио с обязательной опцией выкупа"
    ) == "«Реал» готов отдать Рауля Асенсио в аренду с обязательным выкупом"
    assert clean_text(
        "«Реал» вновь пропускает ключевое собрание Ла Лиги и RFEF"
    ) == "«Реал» снова пропустит встречу Ла Лиги и RFEF"
    assert clean_text(
        "«Реал» и «Галактико» намерены провести важные переговоры с мюнхенской «Баварией» на фоне будущих спекуляций"
    ) == "Олисе обсудит будущее с «Баварией», «Реал» следит за ситуацией"
    assert clean_text(
        "Душан Влахович переходит в «Реал»"
    ) == "Душана Влаховича связывают с «Реалом»"
    assert clean_text(
        "Марк Меншен, эксперт по экономике: «Концерты» Бернабеу «не являются экономической проблемой для«Реала», они приносят 1% дохода, и те, кто зарабатывает деньги, - это артисты»"
    ) == "Эксперт: концерты на «Бернабеу» дают около 1% дохода «Реала»"
    assert clean_text(
        "Верховный суд закрывает ворота на парковках «Бернабеу» и закрывает ресурс «Реал»"
    ) == "Верховный суд отклонил апелляцию «Реала» по парковкам у «Бернабеу»"
    assert clean_text(
        "Герберт Хайнер, президент «Баварии», резко высказался о«Реале»: «Они могут сэкономить усилия»"
    ) == "Президент «Баварии» дал понять: по Олисе «Реалу» будет сложно"
    assert clean_text(
        "Бетис заинтересован в трансфере Фран Гарсии, Реал требует 10 миллионов евро"
    ) == "«Бетис» интересуется Франом Гарсией, «Реал» хочет 10 млн евро"
    assert clean_text(
        "Родриго рассказывает Криштиану Роналду о своей травме колена: «Это немного раздражает и утомляет, но все идет хорошо»"
    ) == "Родриго рассказал о состоянии колена"
    assert clean_text(
        "«Реал» установил цену в 50 миллионов евро за расторжение контракта летом 2025 года"
    ) == "«Реал» оценил возможный уход летнего новичка-2025 в 50 млн евро"
    assert clean_text(
        "Рынок может спровоцировать неожиданный уход в «Реал»"
    ) == "Рынок может спровоцировать неожиданный уход из «Реала»"
    assert clean_text(
        "Хосе Феликс Диас, журналист: «Реал» намерен выложить 100 миллионов за одного из этих трех игроков между Феде Вальверде, Тчуамени и Камавингой»"
    ) == "Хосе Феликс Диас: «Реал» хочет выручить 100 млн евро за Вальверде, Тчуамени или Камавингу"
    assert clean_text(
        "Хосе Феликс Диас, журналист: «Реал» намерен выложить 100 миллионов за одного из этих трех игроков-Феде Вальверде, Тчуамени и Камавингу»"
    ) == "Хосе Феликс Диас: «Реал» хочет выручить 100 млн евро за Вальверде, Тчуамени или Камавингу"
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
        "El Mundial поддерживает Флорентино Переса"
    ) == "Чемпионат мира играет на руку Флорентино Пересу"
    assert clean_text(
        "Майкл Олайс думает о переходе в «Реал»"
    ) == "Майкл Олисе думает о переходе в «Реал»"
    assert clean_text(
        "Реал подтверждает интерес к Майклу Олисе"
    ) == "«Реал» подтверждает интерес к Майклу Олисе"
    assert clean_text(
        "Реал открыт к продаже ключевого полузащитника за 82 миллиона евро"
    ) == "«Реал» готов рассмотреть продажу ключевого полузащитника за 82 млн евро"
    assert clean_text(
        "Реал получит 12, 5 миллионов за Альваро Родригеса"
    ) == "«Реал» получит 12,5 млн евро за Альваро Родригеса"
    assert clean_text(
        "Реал объявил о возможности трансфера Камавинга"
    ) == "«Реал» готов рассмотреть предложения по Камавинге"
    assert clean_text(
        "Заморано, с подписью: «Олисе я бы купил его завтра же для» Мадрида«»"
    ) == "Заморано: я бы купил Олисе для «Реала» уже завтра"
    assert clean_text(
        "Реал опровергает антимадридские высказывания о 'Ла Фабрике'"
    ) == "«Реал» опровергает антимадридский тезис о «Ла Фабрике»"
    assert clean_text(
        "«Реал» опровергает переговоры с Энцо Фернандесом"
    ) == "Официально: «Реал» не ведёт переговоры по Энцо Фернандесу"
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
    assert clean_text(
        "Фальк о ситуации Оливье: «Реал — команда, о которой стоит мечтать»"
    ) == "Фальк об Олисе: «Реал» - клуб мечты"
    assert clean_text(
        "Суд отклонил просьбу Реала о приостановке протокола против насилия Ла Лиги"
    ) == "Суд отклонил просьбу «Реала» приостановить протокол Ла Лиги против домогательств"
    assert clean_text(
        "«Продать Виниция и привезти Олисе? Все говорят» да«»"
    ) == "В Испании обсуждают вариант: продать Винисиуса и подписать Олисе"
    assert clean_text(
        "Феде Вальверде: твёрд в «Реале»"
    ) == "Вальверде твёрдо намерен остаться в «Реале»"
    assert clean_text(
        "Будущее Феде Вальверде в «Реале» подтверждено"
    ) == "Вальверде остаётся в «Реале»"
    assert clean_text(
        "Еще одна жемчужина Фабрики привлекает внимание в Европе"
    ) == "Еще один талант «Ла Фабрики» привлекает внимание в Европе"
    assert clean_text(
        "Томас Ронсеро о звезде чемпионата мира, который хочет подписать Флорентийца: «Я жду его до 31 августа, мечта Олисе-приехать в Мадрид со своим другом Мбаппе»"
    ) == "Томас Ронсеро об Олисе: «Жду его до 31 августа; его мечта - приехать в Мадрид к Мбаппе»"
    assert clean_text(
        "Тчуамени и Скотт входят в шорт-лист полузащитников «Манчестер Юнайтед»."
    ) == "Тчуамени попал в шорт-лист «Манчестер Юнайтед» по центру поля"
    assert clean_text(
        "«Реал» официально опроверг переговоры с игроками"
    ) == "«Реал» напомнил о своих официальных опровержениях по трансферам"
    assert clean_text(
        "Новоиспеченный клуб Ла Лиги ведет переговоры с мадридским «Реалом» о приобретении высококлассного полузащитника академии"
    ) == "Новичок Ла Лиги ведёт переговоры с «Реалом» по талантливому полузащитнику академии"
    assert clean_text(
        "Реал заинтересован в подписании Олисе"
    ) == "«Реал» сохраняет интерес к Олисе"
    assert clean_text(
        "Трансферные сделки Реала активизировались"
    ) == "Трансферы «Реала»: время поджимает"
    assert clean_text(
        "«Реал» доволен своим центром поля, несмотря на невозможность новых приобретений"
    ) == "«Реал» доволен центром поля, несмотря на сложности с новыми трансферами"
    assert clean_text(
        "«Реал» продолжает укрепляться благодаря своей академии"
    ) == "«Реал» продолжает зарабатывать на «Ла Фабрике»"
    assert clean_text(
        "Первый шаг к переквалификации земель Реала в Вальдебебас"
    ) == "Первый шаг к изменению статуса земель «Реала» в Вальдебебасе"
    assert clean_text(
        "«Реал» работает над трансферами"
    ) == "«Реал» получил передышку на трансферном рынке"
    assert clean_text(
        "Un BMV «идеал» для Моуринью"
    ) == "BMV — идеальное трио для Моуринью"
    assert clean_text(
        "Моу и «горячий картофель», который оставляет ему Арбелоа"
    ) == "Моуринью получил от Арбелоа сложную задачу"
    assert clean_text(
        "60 миллионов для завершения обновления защиты и продления контракта с Вини Джуниором"
    ) == "60 млн на обновление защиты и продление Винисиуса"
    assert clean_text(
        "Тчуамени пропустит матч против Парагвая из-за травмы бедра"
    ) == "Тчуамени пропустит матч Франции с Парагваем из-за травмы бедра"
    assert clean_text(
        "Полузащитник мадридского «Реала» активизировал предсезонную подготовку на фоне неопределенного будущего"
    ) == "Камавинга начал предсезонную подготовку на фоне неопределенного будущего"
    assert clean_text(
        "Рубен Мартин о продажах игроков Реала: Флорентино заработает более 200 миллионов"
    ) == "Рубен Мартин: Флорентино может выручить более 200 млн евро на продажах"
    assert clean_text(
        "Марио Хила принес Реалу значительную сумму денег"
    ) == "Марио Хила принесёт «Реалу» солидный доход"
    assert clean_text(
        "Фабрика, которая финансирует «Реал» на 600 миллионов"
    ) == "«Ла Фабрика» принесла «Реалу» около 600 млн евро"
    assert clean_text(
        "Винисиус обсудит продление контракта с «Реалом» после Кубка мира"
    ) == "Винисиус обсудит продление с «Реалом» после ЧМ"
    assert clean_text(
        "«Реал» и Винисиус близки к продлению контракта"
    ) == "«Реал» и Винисиус близки к продлению"
    assert clean_text(
        "Мбаппе выходит из тупика, пропуская Францию мимо Парагвая"
    ) == "Мбаппе вывел Францию в четвертьфинал, забив Парагваю"
    assert clean_text(
        "Открытие Ла Лиги для «Реала» против Реал Сосьедад отменено"
    ) == "Старт «Реала» в Ла Лиге против «Реал Сосьедад» могут перенести"
    assert clean_text(
        "Подтверждена отсрочка дебюта «Реала» в лиге чемпионов"
    ) == "Подтверждён перенос первого матча «Реала» в Ла Лиге"
    assert clean_text(
        "Тчуамени сообщил об травме, которая напугает Реал"
    ) == "Тчуамени сообщил о травме, которая тревожит «Реал»"
    assert clean_text(
        "Защитник Реала рассматривается «Арсенал» ом"
    ) == "Защитник «Реала» попал в список «Арсенала»"
    assert clean_text(
        "Бомбазо Хааланд: «С большой вероятностью буду играть в» Реале«»"
    ) == "Холанда снова связывают с «Реалом»"
    assert clean_text(
        "«Реал» у нужны игроки в аренду для Альваро Арбелоа и Фулхэма"
    ) == "Три игрока «Реала», которым могла бы помочь аренда в «Фулхэм»"
    assert clean_text(
        "Фран Гарсия перешёл в Реал Бетис"
    ) == "Фран Гарсия перешёл в «Бетис»"
    assert clean_text(
        "«Реал» продлил контракт с основным полузащитником до 2031 года"
    ) == "«Реал» продлил Тчуамени до 2031 года"
    assert clean_text(
        "Тчуамени подписал продление контракта с «Реалом» до 2031 года"
    ) == "Тчуамени продлил контракт с «Реалом» до 2031 года"
