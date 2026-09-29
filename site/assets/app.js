// 診断の進行と、結果ページでのクリック計測
(() => {
  const track = (name, params) => {
    if (typeof window.gtag === "function") window.gtag("event", name, params || {});
  };

  // 購入ボタンのクリック（どのタイプのどの本が押されたか）
  document.querySelectorAll("[data-book]").forEach((a) => {
    a.addEventListener("click", () => track("click_book", { book: a.dataset.book }));
  });

  const dataEl = document.getElementById("quiz-data");
  if (!dataEl) return;
  const { questions, order } = JSON.parse(dataEl.textContent);
  const intro = document.getElementById("intro");
  const quiz = document.getElementById("quiz");
  const bar = document.getElementById("bar");
  const count = document.getElementById("count");
  const question = document.getElementById("question");
  const back = document.getElementById("back");
  let answers = [];

  const render = () => {
    const i = answers.length;
    bar.style.width = `${(i / questions.length) * 100}%`;
    count.textContent = `Q${i + 1} / ${questions.length}`;
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
    quiz.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  quiz.querySelectorAll("[data-answer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      answers.push(btn.dataset.answer);
      if (answers.length < questions.length) return render();
      const type = diagnose();
      bar.style.width = "100%";
      track("quiz_complete", { type });
      location.href = `result/${type}/`;
    });
  });

  back.addEventListener("click", () => {
    answers.pop();
    render();
  });
})();
