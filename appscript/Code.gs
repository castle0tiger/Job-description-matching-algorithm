// ============================================================
// JD 후보자 매칭 시스템 - Google Apps Script 백엔드
// ============================================================

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('JD 후보자 매칭 시스템')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getApiKey() {
  const key = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!key) throw new Error('GEMINI_API_KEY가 설정되지 않았습니다. 스크립트 속성을 확인하세요.');
  return key;
}

function callGemini(parts) {
  const apiKey = getApiKey();
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey;

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      contents: [{ parts: parts }]
    }),
    muteHttpExceptions: true
  });

  const data = JSON.parse(response.getContentText());
  if (data.error) throw new Error(data.error.message);
  return data.candidates[0].content.parts[0].text;
}

function extractJson(text) {
  const m1 = text.match(/```json\s*([\s\S]*?)\s*```/);
  if (m1) return JSON.parse(m1[1]);
  const m2 = text.match(/\{[\s\S]*\}/);
  if (m2) return JSON.parse(m2[0]);
  throw new Error('JSON을 찾을 수 없습니다.');
}

// JD 분석
function analyzeJD(base64pdf) {
  try {
    const prompt = '다음 채용공고(JD)를 분석하여 요구사항을 JSON으로 추출하세요. 없는 정보는 null.\n\n반드시 아래 형식으로만 응답하세요:\n```json\n{\n  "position": "직무명",\n  "required_skills": ["스킬1"],\n  "preferred_skills": ["스킬1"],\n  "min_experience_years": 3,\n  "max_experience_years": null,\n  "education": "대졸",\n  "required_certifications": [],\n  "domain": "도메인",\n  "key_responsibilities": ["업무1"],\n  "job_description": "한 줄 요약"\n}\n```';

    const text = callGemini([
      { inline_data: { mime_type: 'application/pdf', data: base64pdf } },
      { text: prompt }
    ]);
    return { success: true, data: extractJson(text) };
  } catch(e) {
    return { success: false, error: e.message };
  }
}

// 이력서 분석
function analyzeResume(base64pdf, filename) {
  try {
    const prompt = '다음 이력서를 분석하여 후보자 정보를 JSON으로 추출하세요. 없는 정보는 null. 경력은 소수 허용, 연봉은 만원 단위 정수.\n\n반드시 아래 형식으로만 응답하세요:\n```json\n{\n  "name": "홍길동",\n  "age": 30,\n  "education": "대졸",\n  "education_major": "컴퓨터공학",\n  "total_experience_years": 5.0,\n  "skills": ["Python"],\n  "certifications": [],\n  "last_salary": 4500,\n  "companies": ["회사명"],\n  "projects": ["프로젝트"],\n  "career_summary": "경력 요약"\n}\n```';

    const text = callGemini([
      { inline_data: { mime_type: 'application/pdf', data: base64pdf } },
      { text: prompt }
    ]);
    const data = extractJson(text);
    data.filename = filename;
    return { success: true, data: data };
  } catch(e) {
    return { success: false, error: e.message, data: { filename: filename, name: filename, skills: [], certifications: [] } };
  }
}

// 후보자 매칭 평가
function matchCandidate(jd, candidate) {
  try {
    const jdSummary = [
      '직무: ' + jd.position,
      '도메인: ' + jd.domain,
      '필수 스킬: ' + (jd.required_skills || []).join(', '),
      '우대 스킬: ' + (jd.preferred_skills || []).join(', '),
      '최소 경력: ' + jd.min_experience_years + '년 이상',
      '요구 학력: ' + (jd.education || '무관'),
      '주요 업무: ' + (jd.key_responsibilities || []).slice(0, 5).join(', ')
    ].join('\n');

    const candidateSummary = [
      '이름: ' + candidate.name,
      '나이: ' + (candidate.age || '미확인') + '세',
      '학력: ' + (candidate.education || '미확인') + ' (' + (candidate.education_major || '') + ')',
      '경력: ' + (candidate.total_experience_years || '미확인') + '년',
      '스킬: ' + (candidate.skills || []).join(', '),
      '자격증: ' + ((candidate.certifications || []).join(', ') || '없음'),
      '경력 요약: ' + (candidate.career_summary || '')
    ].join('\n');

    const prompt = '채용 전문가로서 아래 채용공고와 후보자를 비교하여 평가하세요.\n\n=== 채용공고 ===\n' + jdSummary + '\n\n=== 후보자 ===\n' + candidateSummary + '\n\n반드시 아래 JSON으로만 응답하세요:\n```json\n{\n  "total_score": 85,\n  "skill_match_score": 90,\n  "experience_score": 80,\n  "education_score": 100,\n  "overall_fit": "상",\n  "strengths": ["강점1", "강점2"],\n  "weaknesses": ["약점1"],\n  "recommendation": "적극 추천",\n  "reasoning": "종합 평가 3~5문장"\n}\n```\noverall_fit: "상"/"중"/"하" 중 하나\nrecommendation: "적극 추천"/"추천"/"검토 필요"/"미추천" 중 하나\ntotal_score = 스킬 40% + 경력 35% + 학력 15% + 기타 10%';

    const text = callGemini([{ text: prompt }]);
    return { success: true, data: extractJson(text) };
  } catch(e) {
    return { success: false, error: e.message };
  }
}
