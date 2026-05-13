"""
VN Copy — UI strings for Komaru Anti-Slop · Tiếng Việt
========================================================

Voice rewrite v3 (2026-05-13 evening) — professional balanced:
  - KHÔNG particles trẻ con: "ghê", "đi", "luôn", "thử", "thôi", "vậy"
  - KHÔNG quá formal: "kính mến", "trân trọng", "quý khách"
  - Reference voice: Notion VN, Stripe VN docs, Linear, Substack
  - Câu hoàn chỉnh, không speech-fragment
  - Không "tôi" first-person (đây là sản phẩm, không phải cá nhân)
  - Vẫn KHÔNG em-dash, KHÔNG parallel triples, KHÔNG Anglicism

Reframe-A locked: practical writing self-check, NO legal claim.
Pseudonym TIER 0: no real name / institution.
"""

# ---- Brand frame ----
BRAND_TITLE = "Komaru Anti-Slop · Tiếng Việt"
BRAND_SUBTITLE = "Phát hiện dấu hiệu giọng AI trong văn bản tiếng Việt."
BRAND_FRAME_VN = (
    "Công cụ phân tích văn bản tiếng Việt, phát hiện các cụm từ và cấu "
    "trúc thường gặp ở nội dung do AI tạo. Hỗ trợ người viết tự rà soát "
    "giọng văn trước khi xuất bản."
)

# ---- Page ----
PAGE_TITLE = "Soi văn bản"
PAGE_HEADER = "📝 Soi văn bản"
PAGE_INTRO = (
    "Dán văn bản tiếng Việt vào ô dưới (tối thiểu 100 ký tự). Hệ thống "
    "phân tích theo 3 lớp: cụm từ điển hình của AI, đặc trưng thống kê "
    "về độ đều câu và vốn từ, và đánh giá của Claude (tuỳ chọn)."
)

PASTE_LABEL = "Văn bản cần kiểm tra"
PASTE_PLACEHOLDER = (
    "Bài blog, bài viết mạng xã hội, mô tả sản phẩm, email... "
    "Cần tối thiểu 100 ký tự."
)

RUN_BUTTON = "Kiểm tra"
RUN_BUTTON_LLM = "Kiểm tra (kèm Claude, lâu hơn vài giây)"

# ---- Verdict labels ----
VERDICT_LABELS = {
    "human": ("✅ Tự nhiên", "#16a34a"),
    "mixed": ("🟡 Có dấu hiệu nhẹ", "#f59e0b"),
    "likely_ai": ("🟠 Nhiều dấu hiệu", "#ea580c"),
    "very_likely_ai": ("🔴 Dấu hiệu rõ rệt", "#dc2626"),
}

VERDICT_EXPLANATION = {
    "human": (
        "Văn bản có giọng tự nhiên, không bộc lộ rõ dấu hiệu AI. "
        "Có thể giữ nguyên cách viết hiện tại."
    ),
    "mixed": (
        "Văn bản có một số dấu hiệu giọng AI. Có thể đã chỉnh sửa từ "
        "AI hoặc viết theo template quen thuộc. Tham khảo các điểm "
        "bên dưới để điều chỉnh."
    ),
    "likely_ai": (
        "Văn bản có nhiều dấu hiệu giọng AI: cụm từ sáo rỗng, độ dài "
        "câu đồng đều, tần suất liên từ trang trọng cao. Khuyến nghị "
        "viết lại 30 đến 50 phần trăm nội dung."
    ),
    "very_likely_ai": (
        "Cả 3 lớp đều ghi nhận dấu hiệu giọng AI rõ rệt. Để văn bản "
        "nghe tự nhiên hơn, nên viết lại từ đầu, giữ nội dung và thay "
        "câu chữ."
    ),
}

CONFIDENCE_LABELS = {
    "low": "Thấp",
    "medium": "Trung bình",
    "high": "Cao",
}

# ---- Section labels ----
SEC_OVERALL = "Kết quả"
SEC_LAYERS = "Phân tích theo lớp"
SEC_EVIDENCE = "Các điểm phát hiện"
SEC_RUBRIC = "Đánh giá của Claude"
SEC_SUGGESTIONS = "Gợi ý chỉnh sửa"
SEC_SUGGESTIONS_EMPTY = (
    "Không có gợi ý chỉnh sửa cụ thể — văn bản hiện tại đủ tự nhiên."
)
SUGGESTIONS_INTRO = (
    "Mỗi gợi ý gắn với một dấu hiệu cụ thể trong văn bản. Áp dụng từ "
    "trên xuống (mức nghiêm trọng cao nhất trước)."
)
SUGGESTION_HIT_LABEL = "lượt"

LAYER_NAMES = {
    "regex": "Lớp 1 · Cụm từ",
    "statistical": "Lớp 2 · Thống kê",
    "llm": "Lớp 3 · Claude",
}

# ---- Footer ----
PRIVACY_NOTE = (
    "🔒 **Quyền riêng tư.** Văn bản không được lưu trữ. Khi đóng tab, "
    "nội dung sẽ bị xoá. Mỗi lần phân tích tạo một mã hash SHA-256, "
    "cho phép tái tạo cùng kết quả nếu cần xác thực lại."
)

LIMITATION_NOTE = (
    "ℹ️ **Giới hạn của phương pháp.** Văn bản học thuật chuẩn mực, bản "
    "dịch, hoặc báo cáo theo template chặt chẽ có thể bị nhận nhầm là AI "
    "dù do người viết. Sử dụng kết quả như một góc nhìn tham khảo, "
    "không phải kết luận tuyệt đối."
)

# ---- Pricing copy ----
PRICING_HEADER = "💰 Bảng giá"

PRICING_TIERS = [
    {
        "name": "Free",
        "vnd": "Miễn phí",
        "usd": "Free",
        "limits": "3 lượt mỗi ngày · Lớp 1 và 2",
        "ideal": "Sử dụng không thường xuyên",
    },
    {
        "name": "Pro Monthly",
        "vnd": "350.000 ₫ / tháng",
        "usd": "$19 / tháng",
        "limits": "Không giới hạn · Cả 3 lớp · Tải kết quả · API",
        "ideal": "Marketer, blogger, biên tập viên dùng hàng ngày",
    },
]

PRICING_NOTE_VN = (
    "Giai đoạn beta tháng 5/2026: Pro giảm 30 phần trăm còn 245.000 ₫. "
    "Đăng ký email để nhận thông tin thanh toán khi Pro ra mắt."
)

# ---- Pro waitlist (email-gated, no public payment) ----
WAITLIST_HEADER = "Đăng ký nhận thông báo Pro"
WAITLIST_INTRO = (
    "Pro đang trong giai đoạn beta. Để đăng ký, để lại email bên dưới. "
    "Khi Pro chính thức ra mắt, hệ thống sẽ gửi hướng dẫn thanh toán "
    "(VND qua VietQR hoặc USD qua Stripe) đến email đã đăng ký."
)
WAITLIST_EMAIL_LABEL = "Email"
WAITLIST_EMAIL_PLACEHOLDER = "ban@example.com"
WAITLIST_BUTTON = "Đăng ký Pro"
WAITLIST_PRIVACY = (
    "Email chỉ được sử dụng để gửi thông báo về Pro. Không chia sẻ với "
    "bên thứ ba. Có thể yêu cầu xoá bất cứ lúc nào qua "
    "komarununi.business@gmail.com."
)

# ---- Sample texts ----
SAMPLES = {
    "Quảng cáo Facebook (đậm AI)": (
        "Trong thời đại 4.0, chuyển đổi số đã trở nên ngày càng quan trọng "
        "đối với mọi doanh nghiệp. Hôm nay tôi rất hào hứng được chia sẻ "
        "với các bạn một giải pháp toàn diện giúp tối ưu hóa quy trình. "
        "Tuy nhiên, không phải ai cũng hiểu rõ. Do đó, chúng ta cần lưu ý "
        "rằng quy trình này đem lại trải nghiệm tuyệt vời. Ngoài ra, "
        "đáng chú ý là 100% khách hàng hài lòng. Hãy theo dõi để biết thêm!"
    ),
    "Đoạn blog cá nhân": (
        "Sáng nay đi cà phê với anh bạn cũ. Anh ấy mới chuyển việc, lương "
        "tăng nhẹ nhưng phải làm thứ bảy. Mình nghe xong thấy chán thay. "
        "Đời đi làm mà cuối tuần không còn thì giàu kiểu gì cũng mệt. "
        "Mình bảo: thôi anh thử thương lượng lại cuối tuần nghỉ một, hoặc "
        "remote nửa tuần. Anh ấy gãi đầu, cười, bảo công ty Việt Nam đâu có "
        "kiểu đó dễ. Cũng đúng. Hai anh em ngồi im một lúc. Cà phê nguội."
    ),
    "Tin nhắn CSKH tự động": (
        "Quý khách hàng kính mến, mong quý khách thông cảm vì sự bất tiện. "
        "Theo chính sách của công ty chúng tôi, đơn hàng sẽ được xử lý trong "
        "vòng 24 giờ. Đội ngũ chăm sóc khách hàng của chúng tôi cam kết "
        "đem lại trải nghiệm tuyệt vời cho quý khách. Trân trọng cảm ơn "
        "quý khách đã tin tưởng. Một cách nhanh chóng và hiệu quả, chúng tôi "
        "sẽ phản hồi sớm nhất có thể."
    ),
}
