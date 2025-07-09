document.addEventListener("DOMContentLoaded", function () {
  const forms = document.querySelectorAll("form");

  forms.forEach(form => {
    form.addEventListener("submit", function () {
      const buttons = form.querySelectorAll("button, input[type='submit']");

      buttons.forEach(button => {
        if (button.hasAttribute("data-no-disable")) return; // исключение

        button.disabled = true;
        button.classList.add("disabled");

        if (button.tagName === "BUTTON" || button.type === "submit") {
          button.dataset.originalText = button.innerText;
          button.innerText = "Подождите...";
        }
      });
    });
  });
});