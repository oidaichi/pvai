PV生成AIシステム：ComfyUI エンジン改修要件定義書 (Technical Specification) 
Primary Goal: 視聴維持率(2s)とCTRを最大化する商用動画生成SaaSの構築

1. 改修の目的と方針
ComfyUIを「GUIアプリケーション」から、SaaSのバックエンドとして動作する「ヘッドレスな動画生成マイクロサービス」へ改造する。
Modal環境でのコールドスタート時間短縮、Cloudflare R2 (S3互換) との直接I/O、および指定された最新モデル（Nano Banana Pro, LongCat-Video）の最適化を行う。
1. コアアーキテクチャ改修 (Core Modifications)
2.1 エントリーポイントの刷新 (Headless Execution)
標準の main.py および server.py は常駐型（WebSocket依存）であるため、ModalのServerless実行モデル（Request/Response型）に合わせてエントリーポイントを刷新する。
対象ファイル: main.py, execution.py
要件:
modal_entrypoint.py (新規): GUI配信機能を排除し、APIリクエストを受け取って即座に ExecutionManager を実行する軽量エントリーポイントを作成。
同期実行ロジック: execution.py 内のキューイングシステムをバイパスし、リクエスト → 推論 → 結果返却 を1つの関数呼び出しで完結させる同期実行ラッパーを実装。
メモリ常駐化: Modalの app.cls デコレータを使用し、モデル（Checkpoint, VAE）をメモリにロードした状態を維持するコンテナ設計にする。
2.2 ファイルI/Oのクラウド化 (Cloud Native I/O)
一時的なコンテナ環境であるため、ローカルディスク (input/, output/) への依存を排除する。
対象ファイル: folder_paths.py, nodes.py
実装ノード:
LoadImageFromUrl: S3/R2 Presigned URL または公開URLから画像をオンメモリ (PIL.Image / Tensor) で直接読み込むノード。
SaveVideoToUpload: 生成された .mp4 をディスクに保存せず、メモリバッファ (io.BytesIO) 経由で直接 Cloudflare R2 (S3互換ストレージ) へアップロードするノード。
1. AIモデル・推論エンジンの実装要件
3.1 LongCat-Video (I2V) の統合 [変更]
静止画に物理的に正しい動きを与えるため、Wan2.2に代わり LongCat-Video を採用する。
対象ディレクトリ: custom_nodes/LongCat_Wrapper/ (新規作成)
要件:
Wrapper Node実装: LongCat-Videoの推論コードをComfyUIノードとしてラップする。
物理挙動パラメータ: プロンプトだけでなく、物理演算の強度（水流、揺れなど）を制御する motion_scale や physics_bias といったパラメータを入力ピンとして公開する。
VRAM最適化: A100/A10G環境での動作を保証するため、必要に応じてFP8量子化ロードの実装を行う。
3.2 Nano Banana Pro (T2I) & IP-Adapter
高画質なキーフレーム生成と商品の一貫性維持を行う。
要件:
Nano Banana Pro対応: SDXL/Fluxベースのアーキテクチャ判定を行い、最適なSampler/Scheduler設定をプリセット化する。
IP-Adapter統合: 商品画像（ロゴ・形状）の保持力を高めるため、IPAdapter Plus ノード相当の機能を組み込み、weight パラメータをAPIから調整可能にする。
3.3 音声生成・同期 (Audio Generation)
要件: 動画尺に合わせたBGM/ナレーション生成ノードをワークフロー内に組み込み、映像と長さが一致した状態で出力する。
1. 動画生成モード別 実装要件
ユーザーの3つのニーズに対応するためのワークフローおよびカスタムノード要件。
Case A: インフルエンサー型 (架空人物)
技術: T2I (Nano Banana Pro) + IP-Adapter
実装: テキストプロンプトから人物を生成し、IP-Adapterで商品を持たせる構成。
改修点: 商品と人物の合成精度を高めるため、Inpainting（ReActor等）やMasking処理を自動化するサブグラフを作成する。
Case B: リップシンク型 (特定人物)
技術: LivePortrait または MuseTalk
実装: ComfyUI内に LivePortrait ノードを統合。
改修点:
入力画像（1枚）と生成された音声（Audio）を入力とし、口の動きを同期させた映像を出力するパイプラインを構築。
表情制御パラメータ（笑顔、真剣など）をDirector AIからのJSON指示で変更可能にする。
Case C: ポーズ制御型 (動き指定)
技術: ControlNet (OpenPose/Depth) + Video-to-Video
実装: ユーザー入力動画からControlNetプリプロセッサで動き情報を抽出。
改修点:
LoadVideoFromUrl (リファレンス動画用) の実装。
抽出したPose/Depth情報を LongCat-Video (または互換性のあるV2Vモデル) のConditioningに入力するフローの確立。
1. Director AI & Assembly 連携
5.1 Director Bridge (Middleware)
Director AI (vLLM) が出力するJSON指示書を、ComfyUIのワークフローパラメータに変換する。
実装: middleware/workflow_patcher.py
機能: JSON内の scene_list に基づき、適切なワークフロー（Case A/B/C）を選択し、各ノードのパラメータ（Prompt, Seed, Motion Strength）を動的に書き換えて実行エンジンに渡す。
5.2 Assembly (FFmpeg on Modal)
ComfyUIから出力された複数のカット（映像+音声同期済み）を1本に結合する。
処理: ComfyUIの出力完了トリガーを受け、Modal上のPythonスクリプトが ffmpeg-python を使用して単純結合（concat）を行う。音声ズレのリスクを排除するため、ComfyUI内での尺調整を必須とする。
1. 開発フェーズ
Phase 1: 環境構築 & コア改修: Modal上でのComfyUIヘッドレス起動、Cloudflare R2 (S3) I/Oの実装。
Phase 2: モデル統合: Nano Banana Pro, LongCat-Video のノード実装と動作確認。
Phase 3: モード別ワークフロー構築: Case A, B, C の .json ワークフロー作成とDirector AIとの連携テスト。
Phase 4: 最適化: VRAM使用量の削減、コールドスタート対策、エラーハンドリングの強化。
KPI達成のための技術的注力ポイント:
冒頭2秒維持率: 監督AIの指示に基づき、最初のカットで最も視覚的インパクトの強いエフェクト（LongCat-Videoの物理演算など）を適用する仕組みを作る。
CTR: 商品が正しく、かつ魅力的に描写されるよう、
