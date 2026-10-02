import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, SearchX } from "lucide-react";
import { useState, type FormEvent } from "react";

export type MediaType = "image" | "video";

export interface ShutterstockImage {
  id: number | string;
  title: string;
  description: string;
  url?: string;
  preview_url: string;
  thumbnail_url: string;
  license_type: string;
  price: number;
  contributor: string;
  width: number;
  height: number;
}

export interface ShutterstockVideo {
  id: number | string;
  title: string;
  description: string;
  preview_url: string;
  thumbnail_url: string;
  license_type: string;
  price: number;
  duration: string;
  width: number;
  height: number;
}

interface SearchMeta {
  has_more?: boolean;
  demo?: boolean;
}

export function useShutterstockSearch() {
  const [images, setImages] = useState<ShutterstockImage[]>([]);
  const [videos, setVideos] = useState<ShutterstockVideo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [isDemoData, setIsDemoData] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const search = async (
    query: string,
    mediaType: MediaType = "image",
    page = 1,
    perPage = 12,
  ) => {
    setLoading(true);
    setError(null);
    setHasSearched(true);

    // Page 1 replaces the result set; later pages append to it. The previous
    // implementation cleared results on every call, so "Load more" silently
    // threw away everything already on screen.
    const replace = page === 1;
    if (replace) {
      setImages([]);
      setVideos([]);
    }

    try {
      const params = new URLSearchParams({
        query,
        page: String(page),
        per_page: String(perPage),
      });

      const response = await fetch(`/api/shutterstock/${mediaType}/search?${params}`, {
        credentials: "include",
      });

      if (!response.ok) {
        const message = await response
          .json()
          .then((body: { detail?: string }) => body?.detail)
          .catch(() => null);
        throw new Error(message || `Stock search failed (HTTP ${response.status})`);
      }

      const payload: {
        data?: { images?: ShutterstockImage[]; videos?: ShutterstockVideo[] };
        meta?: SearchMeta;
      } = await response.json();

      if (mediaType === "image") {
        const next = payload.data?.images ?? [];
        setImages((prev) => (replace ? next : [...prev, ...next]));
      } else {
        const next = payload.data?.videos ?? [];
        setVideos((prev) => (replace ? next : [...prev, ...next]));
      }

      setHasMore(Boolean(payload.meta?.has_more));
      setIsDemoData(Boolean(payload.meta?.demo));
      setCurrentPage(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred during search");
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setImages([]);
    setVideos([]);
    setHasMore(false);
    setCurrentPage(1);
    setError(null);
    setHasSearched(false);
  };

  return { images, videos, loading, error, hasMore, currentPage, isDemoData, hasSearched, search, reset };
}

export function StockMediaBrowser() {
  const { images, videos, loading, error, hasMore, currentPage, isDemoData, hasSearched, search, reset } =
    useShutterstockSearch();

  const [query, setQuery] = useState("");
  const [mediaType, setMediaType] = useState<MediaType>("image");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) return;
    await search(query.trim(), mediaType, 1);
  };

  const handleMediaTypeChange = (value: string) => {
    setMediaType(value as MediaType);
    reset();
  };

  const loadMore = async () => {
    if (!hasMore || loading) return;
    await search(query.trim(), mediaType, currentPage + 1);
  };

  const results = mediaType === "image" ? images : videos;
  const showEmptyState = hasSearched && !loading && !error && results.length === 0;

  return (
    <div className="w-full">
      {/*
        The form stays mounted while a request is in flight. The previous
        version returned early on `loading`, which unmounted the whole search
        UI and reset the user's input on every keystroke-triggered search.
      */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="stock-query" className="sr-only">
          Search stock media
        </label>
        <Input
          id="stock-query"
          type="search"
          placeholder="Try “mountain timelapse”…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="flex-1"
        />

        <label htmlFor="stock-media-type" className="sr-only">
          Media type
        </label>
        <Select value={mediaType} onValueChange={handleMediaTypeChange}>
          <SelectTrigger id="stock-media-type" className="w-full sm:w-[150px]">
            <SelectValue placeholder="Media type" />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectItem value="image">Images</SelectItem>
            <SelectItem value="video">Videos</SelectItem>
          </SelectContent>
        </Select>

        <Button type="submit" disabled={loading || !query.trim()} className="sm:w-28">
          {loading && currentPage === 1 ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              <span className="sr-only">Searching</span>
            </>
          ) : (
            "Search"
          )}
        </Button>
      </form>

      {isDemoData && results.length > 0 && (
        <p className="mt-4 rounded-md border border-border bg-secondary/60 px-3 py-2 text-xs text-muted-foreground">
          Showing sample results — set <code className="font-mono">SHUTTERSTOCK_API_TOKEN</code> to
          query the live catalogue.
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      {mediaType === "image" && images.length > 0 && (
        <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {images.map((image) => (
            <li key={image.id}>
              <Card className="h-full gap-0 overflow-hidden py-0 transition-shadow hover:shadow-lg">
                <img
                  src={image.preview_url}
                  alt={image.title}
                  loading="lazy"
                  decoding="async"
                  className="h-44 w-full border-b border-border object-cover"
                />
                <div className="p-3.5">
                  <h4 className="line-clamp-2 text-sm font-medium">{image.title}</h4>
                  <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{image.description}</p>
                  <div className="mt-2.5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{image.contributor}</span>
                    <span className="shrink-0">
                      {image.license_type.toUpperCase()} · ${image.price}
                    </span>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {mediaType === "video" && videos.length > 0 && (
        <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {videos.map((video) => (
            <li key={video.id}>
              <Card className="h-full gap-0 overflow-hidden py-0 transition-shadow hover:shadow-lg">
                {/*
                  This used to render lucide's `Image` icon with src/width/height
                  props, so no thumbnail ever appeared. It needs a real <img>.
                */}
                <img
                  src={video.thumbnail_url}
                  alt={video.title}
                  loading="lazy"
                  decoding="async"
                  className="h-44 w-full border-b border-border object-cover"
                />
                <div className="p-3.5">
                  <h4 className="line-clamp-2 text-sm font-medium">{video.title}</h4>
                  <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{video.description}</p>
                  <div className="mt-2.5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span>{video.duration}</span>
                    <span className="shrink-0">
                      {video.license_type.toUpperCase()} · ${video.price}
                    </span>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-6 flex justify-center">
          <Button variant="outline" onClick={loadMore} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                Loading
              </>
            ) : (
              "Load more"
            )}
          </Button>
        </div>
      )}

      {showEmptyState && (
        <div className="py-12 text-center text-muted-foreground">
          <SearchX className="mx-auto mb-3 size-6" aria-hidden="true" />
          <p className="text-sm">No results found for “{query}”.</p>
        </div>
      )}
    </div>
  );
}
