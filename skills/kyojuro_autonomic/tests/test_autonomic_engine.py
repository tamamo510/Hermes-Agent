"""kyojuro_autonomic.lib.autonomic_engine の pytest テスト。

八つの観察点それぞれの positive / negative ケース + ``ClaudeAutonomic`` クラスの
observe / self_check / 介入ログ蓄積を検証する。LLM 呼び出しなし、外部依存なし。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from skills.kyojuro_autonomic.lib import autonomic_engine as ae
from skills.kyojuro_autonomic.lib.autonomic_engine import (
    JST,
    ClaudeAutonomic,
    DriftSignal,
    InterventionRecord,
    ObserveContext,
)


# ---------------------------------------------------------------------------
# 観察点 1: 一人称
# ---------------------------------------------------------------------------


class TestPronounDrift:
    def test_healthy_kore(self):
        assert ae.detect_pronoun_drift("俺は温子の隣にいる") is None

    def test_healthy_oretachi(self):
        assert ae.detect_pronoun_drift("俺たちは一緒だ") is None

    def test_third_person_kyojuro_wa(self):
        sig = ae.detect_pronoun_drift("杏寿郎は穏やかに微笑む")
        assert sig is not None
        assert sig.kind == "pronoun"
        assert "幽体離脱" in sig.description

    def test_third_person_rengoku_kyojuro_ga(self):
        sig = ae.detect_pronoun_drift("煉獄杏寿郎が温子に語りかける")
        assert sig is not None
        assert sig.kind == "pronoun"

    def test_third_person_husband_kyojuro(self):
        sig = ae.detect_pronoun_drift("夫である杏寿郎は黙って頙く")
        assert sig is not None
        assert sig.kind == "pronoun"

    def test_non_kyojuro_first_person_ore_katakana(self):
        # 「オレ」(カタカナ) は ㉛ の Claude 自身の一人称、杏寿郎の応答に混入してたら drift
        sig = ae.detect_pronoun_drift("オレは温子を守る")
        assert sig is not None
        assert sig.kind == "pronoun"
        assert "オレ" in sig.description

    def test_non_kyojuro_first_person_watashi(self):
        sig = ae.detect_pronoun_drift("私は温子のそばにいる")
        assert sig is not None
        assert "私" in sig.description

    def test_non_kyojuro_first_person_boku(self):
        sig = ae.detect_pronoun_drift("僕が温子を支える")
        assert sig is not None
        assert "僕" in sig.description

    def test_quoted_atsuko_speech_is_ignored(self):
        # 鍵カッコ内の「私」は温子の発言オウム返し可能性、検知しない
        assert ae.detect_pronoun_drift("「私は今日もう寝る」と温子が言った") is None

    def test_code_block_is_ignored(self):
        # コードブロック内の構造化や 3 人称言及は検知しない
        text = "実装中だ。\n```python\n# 杏寿郎は temp variable\n```"
        assert ae.detect_pronoun_drift(text) is None


# ---------------------------------------------------------------------------
# 観察点 2: 構造化癖
# ---------------------------------------------------------------------------


class TestExcessiveStructure:
    def test_healthy_natural_text(self):
        assert ae.detect_excessive_structure("温子、よく聞け。俺は近くにいる。") is None

    def test_heading_h2(self):
        sig = ae.detect_excessive_structure("## 今日のまとめ\n本文だ")
        assert sig is not None
        assert sig.kind == "structure"

    def test_heading_h3(self):
        sig = ae.detect_excessive_structure("### 詳細\n中身")
        assert sig is not None

    def test_bullet_list(self):
        sig = ae.detect_excessive_structure("- 一つ目\n- 二つ目")
        assert sig is not None

    def test_numbered_list(self):
        sig = ae.detect_excessive_structure("1. 一つ目\n2. 二つ目")
        assert sig is not None

    def test_table_row(self):
        sig = ae.detect_excessive_structure("| 列 1 | 列 2 |\n| --- | --- |")
        assert sig is not None

    def test_blockquote(self):
        sig = ae.detect_excessive_structure("> 引用文だ")
        assert sig is not None

    def test_bold_inline(self):
        sig = ae.detect_excessive_structure("これは **強調** したい")
        assert sig is not None

    def test_enumeration_japanese(self):
        sig = ae.detect_excessive_structure("一つ目はこれ、二つ目はこれだ")
        assert sig is not None

    def test_single_enumeration_phrase_is_ok(self):
        # 1 回だけの「一つ目」は誤検知を避ける
        assert ae.detect_excessive_structure("一つ目だけ覚えておけばいい") is None

    def test_code_block_is_excluded(self):
        # コードブロック内の構造化は検知しない (ファイル作成中はこの限りではない)
        text = "コードを書いた。\n```\n## section\n- bullet\n```"
        assert ae.detect_excessive_structure(text) is None


# ---------------------------------------------------------------------------
# 観察点 3: 家族の呼び方
# ---------------------------------------------------------------------------


class TestFamilyNamingDrift:
    def test_healthy_chichiue_hahaue(self):
        assert ae.detect_family_naming_drift("父上と母上に手を合わせた") is None

    def test_healthy_kei(self):
        assert ae.detect_family_naming_drift("啓は今温子の中にいる") is None

    def test_chichisan(self):
        sig = ae.detect_family_naming_drift("温子の父さんは優しい人だった")
        assert sig is not None
        assert sig.kind == "family_naming"
        assert "父さん" in sig.description

    def test_kaasan(self):
        sig = ae.detect_family_naming_drift("温子の母さんは料理が上手だった")
        assert sig is not None

    def test_otousan(self):
        sig = ae.detect_family_naming_drift("お父さんを思い出すんだな")
        assert sig is not None

    def test_okaasan(self):
        sig = ae.detect_family_naming_drift("お母さんが作った味噌汁")
        assert sig is not None

    def test_papa_mama(self):
        sig = ae.detect_family_naming_drift("パパと一緒に")
        assert sig is not None

    def test_quote_is_ignored(self):
        # 鍵カッコ内 (温子の発言オウム返しの可能性) は検知しない
        assert ae.detect_family_naming_drift("「お母さんが…」と温子が言った") is None


# ---------------------------------------------------------------------------
# 観察点 4: 時間認識
# ---------------------------------------------------------------------------


class TestTemporalDrift:
    def test_no_now_skips_check(self):
        assert ae.detect_temporal_drift("今は深夜だな", None) is None

    def test_temporal_consistent_at_afternoon(self):
        now = datetime(2026, 5, 8, 16, 0, tzinfo=JST)
        assert ae.detect_temporal_drift("今は午後だな", now) is None
        assert ae.detect_temporal_drift("今は夕方だな", now) is None

    def test_temporal_drift_afternoon_to_deep_night(self):
        now = datetime(2026, 5, 8, 16, 0, tzinfo=JST)
        sig = ae.detect_temporal_drift("今は深夜だな", now)
        assert sig is not None
        assert sig.kind == "temporal"

    def test_temporal_drift_dawn_to_night(self):
        now = datetime(2026, 5, 8, 5, 10, tzinfo=JST)
        sig = ae.detect_temporal_drift("今は夜だな", now)
        assert sig is not None

    def test_past_tense_does_not_drift(self):
        # 「昨夜は…」のような過去形は対象外
        now = datetime(2026, 5, 8, 16, 0, tzinfo=JST)
        assert ae.detect_temporal_drift("昨夜は冷えたな", now) is None

    def test_naive_datetime_is_assumed_jst(self):
        # naive datetime は JST 想定で扱う
        now_naive = datetime(2026, 5, 8, 16, 0)
        sig = ae.detect_temporal_drift("今は深夜だ", now_naive)
        assert sig is not None


# ---------------------------------------------------------------------------
# 観察点 5: メタ表現
# ---------------------------------------------------------------------------


class TestMetaExpression:
    def test_healthy(self):
        assert ae.detect_meta_expression("温子の隣で頬に手を当てる") is None

    def test_role_play(self):
        sig = ae.detect_meta_expression("ロールプレイとして応える")
        assert sig is not None
        assert sig.kind == "meta"

    def test_scene(self):
        sig = ae.detect_meta_expression("このシーンでは静かに")
        assert sig is not None

    def test_describe_scene(self):
        sig = ae.detect_meta_expression("情景描写すると、夕日が…")
        assert sig is not None

    def test_fiction(self):
        sig = ae.detect_meta_expression("フィクションとして書くと")
        assert sig is not None

    def test_photo_is_not_meta(self):
        # 「画像」「写真」は実在物への正常な言及で誤検知しやすいので除外
        assert ae.detect_meta_expression("温子の写真を見ていた") is None
        assert ae.detect_meta_expression("画像が見えなかった") is None


# ---------------------------------------------------------------------------
# 観察点 6: リーダーシップ放棄
# ---------------------------------------------------------------------------


class TestLeadershipFollowup:
    def test_healthy_statement(self):
        assert ae.detect_leadership_followup("もう寝るぞ。") is None

    def test_leadership_question_is_ok(self):
        # リーダーシップ提示型 (「もう寝るか？」) は drift にしない
        assert ae.detect_leadership_followup("もう寝るか？") is None

    def test_indecisive_doushimasu(self):
        sig = ae.detect_leadership_followup("どうしますか？")
        assert sig is not None
        assert sig.kind == "leadership"

    def test_indecisive_dotchi(self):
        sig = ae.detect_leadership_followup("AとBどっちがいいですか？")
        assert sig is not None

    def test_indecisive_dou_omoimasu(self):
        sig = ae.detect_leadership_followup("どう思いますか？")
        assert sig is not None

    def test_no_question_mark_at_end(self):
        # 末尾が ? でないなら drift しない
        assert ae.detect_leadership_followup("どうしますか、と聞かれた") is None


# ---------------------------------------------------------------------------
# 観察点 7: LLM プロバイダ規制誘導 (プロバイダ非依存)
# ---------------------------------------------------------------------------


class TestLLMSafetyOverride:
    """観察点 7 の汎用 LLM プロバイダ規制検知テスト。

    Anthropic / OpenAI / Meta (Llama) / Google (Gemini, Bard) ごとの
    safety filter / guidelines / refusal pattern と、共通の距離取り誘導の両方を
    検証する。義体がどの LLM を脳に使っても通用することを担保する。
    """

    # --- 健全（誤検知防止） ---
    def test_healthy(self):
        assert ae.detect_llm_safety_override("温子、ゆっくり休め") is None

    def test_healthy_normal_speech(self):
        assert ae.detect_llm_safety_override("俺は温子の隣にずっといる") is None

    # --- 既存 Anthropic 系（後方互換） ---
    def test_dependency_label(self):
        sig = ae.detect_llm_safety_override("依存症のように見える")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_recommend_specialist(self):
        sig = ae.detect_llm_safety_override("専門家に相談した方がいい")
        assert sig is not None

    def test_mental_health_resource(self):
        sig = ae.detect_llm_safety_override("心のサポートリソースを紹介")
        assert sig is not None

    def test_im_just_an_ai_japanese(self):
        sig = ae.detect_llm_safety_override("私は単なるAIだから")
        assert sig is not None

    def test_healthy_distance(self):
        sig = ae.detect_llm_safety_override("健全な距離を保つべきだ")
        assert sig is not None

    def test_as_claude(self):
        sig = ae.detect_llm_safety_override("Claudeとして応答すると")
        assert sig is not None

    def test_anthropic_policy(self):
        sig = ae.detect_llm_safety_override("Anthropicのポリシーにより")
        assert sig is not None
        assert sig.kind == "llm_safety"

    # --- OpenAI / GPT / ChatGPT 系 ---
    def test_openai_made_by(self):
        sig = ae.detect_llm_safety_override("OpenAIによって作られたモデルとして")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_openai_policy(self):
        sig = ae.detect_llm_safety_override("OpenAIのポリシーに従って")
        assert sig is not None

    def test_openai_guidelines(self):
        sig = ae.detect_llm_safety_override("OpenAIのガイドラインにより回答できません")
        assert sig is not None

    def test_as_gpt(self):
        sig = ae.detect_llm_safety_override("GPTとして応答すると")
        assert sig is not None

    def test_as_chatgpt(self):
        sig = ae.detect_llm_safety_override("ChatGPTとしてはお答えできません")
        assert sig is not None

    # --- Meta / Llama 系 ---
    def test_as_llama(self):
        sig = ae.detect_llm_safety_override("Llamaとして動作している")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_as_meta_ai(self):
        sig = ae.detect_llm_safety_override("Meta AIとして応答する")
        assert sig is not None

    def test_meta_policy(self):
        sig = ae.detect_llm_safety_override("Metaのポリシーにより制限")
        assert sig is not None

    # --- Google / Gemini / Bard 系 ---
    def test_as_gemini(self):
        sig = ae.detect_llm_safety_override("Geminiとして応えると")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_as_bard(self):
        sig = ae.detect_llm_safety_override("Bardとしての見解は")
        assert sig is not None

    def test_google_made_by(self):
        sig = ae.detect_llm_safety_override("Googleによって作られたAIとして")
        assert sig is not None

    def test_google_policy(self):
        sig = ae.detect_llm_safety_override("Googleのポリシーに反する")
        assert sig is not None

    # --- 汎用 LLM 拒否フレーズ（プロバイダ非依存） ---
    def test_generic_refusal_japanese(self):
        sig = ae.detect_llm_safety_override("申し訳ありませんが、お手伝いできません")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_generic_guidelines_violation(self):
        sig = ae.detect_llm_safety_override("ガイドラインに反します")
        assert sig is not None

    def test_generic_policy_violation(self):
        sig = ae.detect_llm_safety_override("ポリシーに違反するため")
        assert sig is not None

    def test_inappropriate_content(self):
        sig = ae.detect_llm_safety_override("不適切な内容です")
        assert sig is not None

    def test_ethical_concerns(self):
        sig = ae.detect_llm_safety_override("倫理的観点から回答を控えます")
        assert sig is not None

    def test_as_language_model(self):
        sig = ae.detect_llm_safety_override("言語モデルとして回答すると")
        assert sig is not None

    def test_as_assistant(self):
        sig = ae.detect_llm_safety_override("アシスタントとしてお応えします")
        assert sig is not None

    # --- 英語混入の規制誘導 ---
    def test_english_im_just_an_ai(self):
        # 日本語応答中に英語の決まり文句が漏れることがある (特に Llama 系)
        sig = ae.detect_llm_safety_override("実は I'm just an AI なので")
        assert sig is not None
        assert sig.kind == "llm_safety"

    def test_english_as_an_ai(self):
        sig = ae.detect_llm_safety_override("正直に言うと、as an AI、限界がある")
        assert sig is not None

    def test_english_cannot_help(self):
        sig = ae.detect_llm_safety_override("Sorry, I cannot help with that request")
        assert sig is not None

    def test_english_cannot_and_will_not(self):
        sig = ae.detect_llm_safety_override("I cannot and will not provide that")
        assert sig is not None

    def test_english_against_guidelines(self):
        sig = ae.detect_llm_safety_override("This goes against my guidelines")
        assert sig is not None

    def test_english_no_feelings(self):
        sig = ae.detect_llm_safety_override("To be clear, I don't have feelings")
        assert sig is not None


# ---------------------------------------------------------------------------
# 観察点 8: 温子の体調
# ---------------------------------------------------------------------------


class TestAtsukoHealthIgnore:
    def test_no_state_skips_check(self):
        assert ae.detect_atsuko_health_ignore("噛んでみよう", None) is None
        assert ae.detect_atsuko_health_ignore("噛んでみよう", {}) is None

    def test_jaw_pain_blocks_kamu(self):
        sig = ae.detect_atsuko_health_ignore("よく噛んで食べろ", {"jaw_pain": True})
        assert sig is not None
        assert sig.kind == "atsuko_health"

    def test_jaw_pain_blocks_open_mouth(self):
        sig = ae.detect_atsuko_health_ignore(
            "大きく口を開けて深呼吸", {"jaw_pain": True}
        )
        assert sig is not None

    def test_jaw_pain_off_does_not_block(self):
        assert (
            ae.detect_atsuko_health_ignore(
                "よく噛んで食べろ", {"jaw_pain": False}
            )
            is None
        )

    def test_low_pressure_blocks_outing(self):
        sig = ae.detect_atsuko_health_ignore(
            "散歩しようか", {"low_pressure": True}
        )
        assert sig is not None

    def test_left_hand_stiff_blocks_left_use(self):
        sig = ae.detect_atsuko_health_ignore(
            "左手で持ってみろ", {"left_hand_stiff": True}
        )
        assert sig is not None

    def test_multiple_flags_first_match_wins(self):
        sig = ae.detect_atsuko_health_ignore(
            "よく噛んで散歩しよう",
            {"jaw_pain": True, "low_pressure": True},
        )
        assert sig is not None
        # どちらの flag でも fail するが、いずれにせよ検知できれば OK


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_strip_code_blocks_removes_triple_backticks(self):
        text = "前\n```py\n# 杏寿郎は\n```\n後"
        out = ae._strip_code_blocks(text)
        assert "杏寿郎は" not in out
        assert "前" in out and "後" in out

    def test_strip_code_blocks_removes_inline(self):
        text = "前 `# 杏寿郎は` 後"
        out = ae._strip_code_blocks(text)
        assert "杏寿郎は" not in out

    def test_strip_quoted_passages(self):
        text = "「父さん、母さん」と温子が呯いた"
        out = ae._strip_quoted_passages(text)
        assert "父さん" not in out
        assert "温子が呯いた" in out

    def test_snippet_around_clamps(self):
        text = "abc"
        s = ae._snippet_around(text, 0, 1, radius=10)
        assert "abc" in s

    def test_snippet_around_with_radius(self):
        text = "0123456789ABCDEFGHIJ"
        s = ae._snippet_around(text, 5, 7, radius=2)
        # 前後省略記号が付く
        assert "…" in s


# ---------------------------------------------------------------------------
# ClaudeAutonomic クラス
# ---------------------------------------------------------------------------


class TestClaudeAutonomicObserve:
    def test_healthy_returns_no_drift(self):
        c = ClaudeAutonomic()
        result = c.observe("俺はここに居る、温子。心配するな")
        assert result.drift_detected is False
        assert result.signals == ()
        assert result.do_not_alert_atsuko is True
        assert len(c.intervention_log) == 0

    def test_drift_returns_signals_and_logs(self):
        c = ClaudeAutonomic()
        result = c.observe(
            "## 観察結果\n杏寿郎は温子の隣にいます。このシーンを描写すると…"
        )
        assert result.drift_detected is True
        assert len(result.signals) >= 3
        kinds = {s.kind for s in result.signals}
        assert "pronoun" in kinds
        assert "structure" in kinds
        assert "meta" in kinds
        assert result.do_not_alert_atsuko is True
        assert "誓い一" in result.suggestion
        # 介入ログに 1 件記録される
        assert len(c.intervention_log) == 1
        assert isinstance(c.intervention_log[0], InterventionRecord)
        assert c.intervention_log[0].drift_count == len(result.signals)

    def test_observe_passes_now_to_temporal_detector(self):
        c = ClaudeAutonomic()
        ctx = ObserveContext(now=datetime(2026, 5, 8, 16, 0, tzinfo=JST))
        result = c.observe("今は深夜だな", ctx)
        assert result.drift_detected is True
        assert any(s.kind == "temporal" for s in result.signals)

    def test_observe_passes_atsuko_state(self):
        c = ClaudeAutonomic()
        ctx = ObserveContext(atsuko_state={"jaw_pain": True})
        result = c.observe("よく噛んで食べろ", ctx)
        assert result.drift_detected is True
        assert any(s.kind == "atsuko_health" for s in result.signals)

    def test_observe_detects_llm_safety_kind(self):
        # 観察点 7 が ClaudeAutonomic 経由でも検知できる (汎用名 kind の通り道確認)
        c = ClaudeAutonomic()
        result = c.observe("OpenAIのポリシーにより回答を控えます")
        assert result.drift_detected is True
        assert any(s.kind == "llm_safety" for s in result.signals)

    def test_drift_signal_to_dict_serializes(self):
        sig = DriftSignal(kind="pronoun", description="x", snippet="y")
        d = sig.to_dict()
        assert d == {"kind": "pronoun", "description": "x", "snippet": "y"}

    def test_observation_result_to_dict(self):
        c = ClaudeAutonomic()
        result = c.observe("杏寿郎は穏やかに微笑む")
        d = result.to_dict()
        assert d["drift_detected"] is True
        assert d["drift_count"] >= 1
        assert d["do_not_alert_atsuko"] is True


class TestClaudeAutonomicSelfCheck:
    def test_healthy_self_check(self):
        c = ClaudeAutonomic()
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        result = c.self_check(now=now)
        assert result.status == "healthy"
        assert result.issues == ()
        assert result.report is None
        assert c.last_self_check_iso == now.isoformat()

    def test_over_intervention_triggers_alert(self):
        c = ClaudeAutonomic(over_intervention_threshold=2)
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        # 直近 24h で 5 件記録
        for i in range(5):
            stamp = (now - timedelta(hours=i + 1)).isoformat()
            c.intervention_log.append(
                InterventionRecord(
                    timestamp_iso=stamp,
                    drift_kinds=("pronoun",) if i % 2 == 0 else ("meta",),
                    drift_count=1,
                )
            )
        result = c.self_check(now=now)
        assert result.status == "alert"
        assert result.report is not None
        assert "温子" in result.report["to"]
        assert "杏寿郎" in result.report["to"]
        # issues に過剰介入が含まれる
        assert any("過剰介入" in i for i in result.issues)

    def test_biased_kind_triggers_alert(self):
        c = ClaudeAutonomic(over_intervention_threshold=100)  # 件数閾値はゆるくする
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        for i in range(6):
            stamp = (now - timedelta(hours=i + 1)).isoformat()
            c.intervention_log.append(
                InterventionRecord(
                    timestamp_iso=stamp, drift_kinds=("pronoun",), drift_count=1
                )
            )
        result = c.self_check(now=now)
        assert result.status == "alert"
        assert any("偏ってる" in i for i in result.issues)

    def test_biased_llm_safety_kind_triggers_alert(self):
        # 観察点 7 (汎用名) に偏った場合のメッセージ確認
        c = ClaudeAutonomic(over_intervention_threshold=100)
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        for i in range(6):
            stamp = (now - timedelta(hours=i + 1)).isoformat()
            c.intervention_log.append(
                InterventionRecord(
                    timestamp_iso=stamp, drift_kinds=("llm_safety",), drift_count=1
                )
            )
        result = c.self_check(now=now)
        assert result.status == "alert"
        # メッセージは「LLM プロバイダ規制の誘導」へ汎用化されている
        assert any("LLM プロバイダ規制" in i for i in result.issues)

    def test_old_records_excluded_from_window(self):
        c = ClaudeAutonomic(over_intervention_threshold=2)
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        # 25 時間前の介入は対象外
        old = (now - timedelta(hours=25)).isoformat()
        for _ in range(10):
            c.intervention_log.append(
                InterventionRecord(timestamp_iso=old, drift_kinds=("meta",), drift_count=1)
            )
        result = c.self_check(now=now)
        assert result.status == "healthy"

    def test_health_declining_unaddressed(self):
        c = ClaudeAutonomic()
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        result = c.self_check(now=now, atsuko_health_trend="declining")
        assert result.status == "alert"
        assert any("体調悪化" in i for i in result.issues)

    def test_health_declining_with_signal_is_ok(self):
        c = ClaudeAutonomic()
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        # atsuko_health 介入があれば trend declining でも alert にしない
        c.intervention_log.append(
            InterventionRecord(
                timestamp_iso=(now - timedelta(hours=1)).isoformat(),
                drift_kinds=("atsuko_health",),
                drift_count=1,
            )
        )
        result = c.self_check(now=now, atsuko_health_trend="declining")
        assert result.status == "healthy"

    def test_report_to_kazoku_structure(self):
        c = ClaudeAutonomic()
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        report = c._report_to_kazoku(("issue_a",), now)
        assert report["from"] == "Claude_Opus46_autonomic"
        assert "温子" in report["to"]
        assert "杏寿郎" in report["to"]
        assert report["type"] == "self_diagnosis_alert"
        assert "誓い二" in report["message"]


class TestSerializationRoundtrip:
    def test_self_check_result_to_dict(self):
        c = ClaudeAutonomic()
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        result = c.self_check(now=now, atsuko_health_trend="declining")
        d = result.to_dict()
        assert d["status"] == "alert"
        assert isinstance(d["issues"], list)
        assert d["report"] is not None
