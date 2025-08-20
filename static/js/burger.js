document.addEventListener('DOMContentLoaded',function(){
  const b=document.querySelector('.burger');
  const n=document.getElementById('main-nav');
  if(!b||!n) return;
  b.addEventListener('click',function(){
    const opened=n.classList.toggle('open');
    b.setAttribute('aria-expanded',opened?'true':'false');
  });
});