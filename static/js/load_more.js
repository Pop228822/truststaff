document.addEventListener("DOMContentLoaded", () => {
  const loadMoreBtn = document.getElementById("load-more-btn");
  if (!loadMoreBtn) return;  // если has_more == False, кнопки нет

  // считываем data-* атрибуты
  let skip = parseInt(loadMoreBtn.dataset.skip, 10);
  const limit = parseInt(loadMoreBtn.dataset.limit, 10);

  loadMoreBtn.addEventListener("click", async () => {
    // Увеличиваем skip
    skip += limit;

    // partial=1 → мы хотим вернуть только список <li>
    // (без обёртки, чтобы вставить в конец <ul>)
    const url = `/admin/users/list?skip=${skip}&limit=${limit}&partial=1`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        console.error("Ошибка загрузки пользователей", response.status);
        return;
      }
      const html = await response.text();

      // Вставляем в конец текущего <ul>
      const ul = document.querySelector(".record-form ul");
      if (ul && html.trim()) {
        ul.insertAdjacentHTML("beforeend", html);
      }

      // Если ничего не пришло, убираем кнопку
      if (!html.trim()) {
        loadMoreBtn.remove();
      }
    } catch (err) {
      console.error("Ошибка fetch:", err);
    }
  });
});
