// Plain-language names and one-line explanations for Instagram words. Used by <Explain> and the glossary.

export interface Term {
  label: string; // what we show in the UI
  ig?: string; // what Instagram calls it, when different
  short: string; // one line, no jargon
}

export const GLOSSARY: Record<string, Term> = {
  reel: { label: "Reel", short: "A short vertical video (up to 3 minutes). Reels are how new people find you." },
  post: { label: "Post", short: "Anything you put on your profile: a reel, a photo or a carousel." },
  carousel: { label: "Carousel", short: "A post with 2 to 10 photos or videos people swipe through, like slides." },
  story: { label: "Story", short: "A photo or video that disappears after 24 hours." },
  views: { label: "Plays", ig: "Views", short: "How many times your reel started playing. One person can play it many times." },
  reach: { label: "People reached", ig: "Reach / Accounts reached", short: "Different people who saw it at least once." },
  likes: { label: "Likes", short: "People who tapped the heart." },
  comments: { label: "Comments", short: "Messages people wrote under your post. Questions here are great next-reel ideas." },
  shares: { label: "Shares", ig: "Shares / Sends", short: "Times someone sent your post to a friend or their story. The strongest sign people loved it." },
  saves: { label: "Saves", ig: "Saved", short: "People who bookmarked it to come back later. Means it was useful." },
  per_1k: { label: "per 1,000 people reached", short: "Out of every 1,000 people who saw it. Lets you compare small and big posts fairly." },
  engagement: { label: "Engagement", short: "Any action on your post: likes, comments, shares and saves added up." },
  interactions: { label: "Interactions", ig: "Total interactions", short: "Likes + comments + shares + saves on a post." },
  followers: { label: "Followers", short: "People who follow you and see your posts in their feed." },
  follows: { label: "New follows", short: "People who started following you." },
  profile_visits: { label: "Profile visits", short: "Times someone opened your profile page." },
  hook: { label: "Hook", short: "The first 1-2 seconds (first line) of a reel. Its only job: stop the scroll." },
  caption: { label: "Caption", short: "The text under your post. Only the first ~125 characters show before '… more'." },
  hashtag: { label: "Hashtag", short: "A #word that labels your post. 3-5 relevant ones are plenty." },
  cta: { label: "Call to action", ig: "CTA", short: "The one thing you ask people to do, e.g. 'Save this' or 'Send to a friend'." },
  insights: { label: "Insights", short: "Instagram's numbers about your posts and followers." },
  watch_time: { label: "Average watch time", short: "How many seconds people watched, on average, before scrolling away." },
  retention: { label: "How much they watched", short: "Average seconds watched compared to the reel's length. Low = people leave early, usually a weak hook." },
  multiple: { label: "vs your usual", short: "2x means twice the plays of your typical reel. Your own posts are the yardstick." },
  outlier: { label: "Breakout reel", short: "A reel that did 3x or more your usual. A lead to follow up, not a rule." },
  confidence: { label: "How sure", short: "Based on how many of your posts back it up. 'Early hunch' = only a few posts." },
  sample: { label: "Based on", short: "How many of your posts or items the number comes from." },
  audience: { label: "Who it's for", short: "The group of people a post is aimed at, e.g. beginners or job seekers." },
  online_hours: { label: "When followers are online", short: "Hours of the day your followers open Instagram the most (Instagram shares this at 100+ followers)." },
  collection: { label: "Collection", short: "A folder you made for saved posts on Instagram, e.g. 'AI tools'." },
  sync: { label: "Update from Instagram", ig: "Sync", short: "Fetches your latest numbers from Instagram. Read-only." },
  publish: { label: "Post to Instagram", ig: "Publish", short: "Actually puts the post live. Always needs your explicit approval here." },
  demo: { label: "Sample data", ig: "Demo", short: "Made-up numbers so you can try the app before connecting." },
  inferred: { label: "Guessed", ig: "Inferred", short: "Worked out from keywords, not told to us by Instagram. Treat as a hint." },
  format: { label: "Format", short: "How the reel is made: talking to camera, motion graphics, screen recording…" },
  shareability: { label: "Shareability", short: "An estimate of how 'send-to-a-friend' the wording is. Not a prediction." },
};

export function term(key: string): Term {
  return GLOSSARY[key] ?? { label: key.replace(/_/g, " "), short: "" };
}
