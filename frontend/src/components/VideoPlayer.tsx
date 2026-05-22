type Props = {
  src: string | null;
};

export function VideoPlayer({ src }: Props) {
  if (!src) {
    return (
      <div className="video-player video-player--empty">
        <p>Your karaoke video will appear here when processing finishes.</p>
      </div>
    );
  }

  return (
    <div className="video-player">
      <video className="video-player__el" controls src={src} playsInline>
        <track kind="captions" />
      </video>
    </div>
  );
}
