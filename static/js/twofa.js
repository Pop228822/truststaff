// static/js/twofa.js

// Функция инициализации таймера (та же, что и раньше)
function initResendTimer(remainSeconds) {
    const resendButton = document.getElementById("resend-button");
    const countdownElem = document.getElementById("resend-countdown");
    if (!resendButton || !countdownElem) return;

    if (remainSeconds <= 0) return; // Ноль или отрицательно — сразу ничего не делаем

    // Блокируем кнопку
    resendButton.disabled = true;

    let remaining = remainSeconds;
    countdownElem.textContent = `Повторная отправка будет доступна через ${remaining} сек.`;

    const interval = setInterval(() => {
        remaining--;
        countdownElem.textContent = `Повторная отправка будет доступна через ${remaining} сек.`;

        if (remaining <= 0) {
            clearInterval(interval);
            countdownElem.textContent = "";
            resendButton.disabled = false;
        }
    }, 1000);
}

// Подписываемся на событие DOMContentLoaded, чтобы код запустился после загрузки страницы
document.addEventListener("DOMContentLoaded", () => {
    // Ищем элемент-обёртку
    const wrapper = document.getElementById("twofa-wrapper");
    if (!wrapper) return;

    // Читаем атрибут data-remain-seconds
    const remainSecondsAttr = wrapper.getAttribute("data-remain-seconds");
    const remainSeconds = parseInt(remainSecondsAttr, 10) || 0;

    // Инициализируем таймер
    initResendTimer(remainSeconds);
});
