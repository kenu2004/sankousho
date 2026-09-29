// 診断の進行、表示のふわり、結果ページでのクリック計測
(() => {
  const track = (name, params) => {
    if (typeof window.gtag === "function") window.gtag("event", name, params || {});
  };

  // スクロールで見えたら表示する（動きはこれだけ）
  const reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("is-visible"));
  }

  // 購入ボタンのクリック（どのタイプのどの本が押されたか）
  document.querySelectorAll("[data-book]").forEach((a) => {
    a.addEventListener("click", () => track("click_book", { book: a.dataset.book }));
  });

  const dataEl = document.getElementById("quiz-data");
  if (!dataEl) return;
  const { questions, order } = JSON.parse(dataEl.textContent);
  const KANJI = "一二三四五六七八九十";
  const intro = document.getElementById("intro");
  const quiz = document.getElementById("quiz");
  const num = document.getElementById("num");
  const dots = [...document.querySelectorAll("#dots li")];
  const question = document.getElementById("question");
  const back = document.getElementById("back");
  let answers = [];

  const render = () => {
    const i = answers.length;
    num.textContent = `第${KANJI[i] || i + 1}問`;
    dots.forEach((d, j) => {
      d.classList.toggle("done", j < i);
      d.classList.toggle("now", j === i);
    });
    question.textContent = questions[i].text;
    back.hidden = i === 0;
    question.classList.remove("is-in");
    void question.offsetWidth; // アニメーションをやり直す
    question.classList.add("is-in");
  };

  // build.py の diagnose() と同じ判定。同点なら order の先にあるタイプ
  const diagnose = () => {
    const score = Object.fromEntries(order.map((t) => [t, 0]));
    answers.forEach((ans, i) => {
      for (const [t, pt] of Object.entries(questions[i][ans])) score[t] += pt;
    });
    return order.reduce((best, t) => (score[t] > score[best] ? t : best), order[0]);
  };

  document.getElementById("start").addEventListener("click", () => {
    intro.hidden = true;
    quiz.hidden = false;
    answers = [];
    render();
    track("quiz_start");
    quiz.scrollIntoView({ block: "start" });
  });

  quiz.querySelectorAll("[data-answer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      answers.push(btn.dataset.answer);
      btn.blur();
      if (answers.length < questions.length) return render();
      dots.forEach((d) => { d.classList.remove("now"); d.classList.add("done"); });
      const type = diagnose();
      track("quiz_complete", { type });
      location.href = `result/${type}/`;
    });
  });

  back.addEventListener("click", () => {
    answers.pop();
    render();
  });
})();
