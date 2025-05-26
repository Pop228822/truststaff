console.log("autocomplete.js loaded!");
const inputEl = document.getElementById('company_name');
const listEl = document.getElementById('org-suggestions');
const cityEl = document.getElementById('city');
const innEl = document.getElementById('inn_or_ogrn');

let timerId;

inputEl.addEventListener('input', () => {
  const query = inputEl.value.trim();
  if (query.length < 2) {
    listEl.innerHTML = "";
    return;
  }

  clearTimeout(timerId);
  timerId = setTimeout(() => {
    loadSuggestions(query);
  }, 300);
});

async function loadSuggestions(query) {
  try {
    const response = await fetch(`/autocomplete/orgs?query=${encodeURIComponent(query)}`);
    const data = await response.json();
    listEl.innerHTML = "";
    data.results.forEach(org => {
      const li = document.createElement('li');
      // Пример: org.display может содержать строки,
      // split('\n') => join('<br>') если нужно

      li.innerHTML = org.display.replace('\n', '<br>');

      li.addEventListener('click', () => {
        inputEl.value = org.value;
        innEl.value = org.inn;
        cityEl.value = org.address;
        listEl.innerHTML = "";
      });

      listEl.appendChild(li);
    });
  } catch (err) {
    console.error(err);
  }
}
