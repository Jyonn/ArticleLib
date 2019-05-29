let start = document.getElementById('start');
let input = document.getElementsByTagName('input')[0];
let show = document.getElementById('html');

let buttonActive = true;

start.addEventListener('click', () => {
    if (!buttonActive) {
        return;
    }
    start.innerText = '正在请求…';
    buttonActive = false;
    Request.post('/v1/weixin', {url: input.value})
        .then(resp => {
            deactivate(start);
            activate(show);
            show.innerText = resp.content;
            buttonActive = true;
        })
        .catch(() => {
            start.innerText = '请求失败…';
        })
});
