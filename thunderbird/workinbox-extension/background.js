const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";
const REQUESTED_TAG = "wib-requested";
const WAITING_ACTION_TAG = "wib-waiting-action";
const WORK_VIEW_TAB_STORAGE_KEY = "workinboxWorkViewTabId";

const WORK_VIEW_TAGS = {
  answer: "wib-answer",
};

function messageIdCandidates(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return [];
