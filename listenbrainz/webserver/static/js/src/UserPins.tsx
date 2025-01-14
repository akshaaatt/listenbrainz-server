/* eslint-disable jsx-a11y/anchor-is-valid */

import * as ReactDOM from "react-dom";
import * as React from "react";

import { isEqual } from "lodash";
import ErrorBoundary from "./ErrorBoundary";
import GlobalAppContext, { GlobalAppContextT } from "./GlobalAppContext";
import {
  WithAlertNotificationsInjectedProps,
  withAlertNotifications,
} from "./AlertNotificationsHOC";

import APIServiceClass from "./APIService";
import BrainzPlayer from "./BrainzPlayer";
import Loader from "./components/Loader";
import PinnedRecordingCard from "./PinnedRecordingCard";
import { getPageProps, getListenablePin } from "./utils";

export type UserPinsProps = {
  user: ListenBrainzUser;
  pins: PinnedRecording[];
  totalCount: number;
  profileUrl?: string;
} & WithAlertNotificationsInjectedProps;

export type UserPinsState = {
  direction: BrainzPlayDirection;
  pins: PinnedRecording[];
  page: number;
  maxPage: number;
  loading: boolean;
};

export default class UserPins extends React.Component<
  UserPinsProps,
  UserPinsState
> {
  static contextType = GlobalAppContext;
  declare context: React.ContextType<typeof GlobalAppContext>;

  private DEFAULT_PINS_PER_PAGE = 25;

  constructor(props: UserPinsProps) {
    super(props);
    const { totalCount } = this.props;
    this.state = {
      maxPage: Math.ceil(totalCount / this.DEFAULT_PINS_PER_PAGE),
      page: 1,
      pins: props.pins || [],
      loading: false,
      direction: "down",
    };
  }

  async componentDidMount(): Promise<void> {
    // Listen to browser previous/next events and load page accordingly
    window.addEventListener("popstate", this.handleURLChange);
    this.handleURLChange();
  }

  componentWillUnmount() {
    window.removeEventListener("popstate", this.handleURLChange);
  }

  // pagination functions
  handleURLChange = async (): Promise<void> => {
    const { page, maxPage } = this.state;
    const url = new URL(window.location.href);

    if (url.searchParams.get("page")) {
      let newPage = Number(url.searchParams.get("page"));
      if (newPage === page) {
        // page didn't change
        return;
      }
      newPage = Math.max(newPage, 1);
      newPage = Math.min(newPage, maxPage);
      await this.getPinsFromAPI(newPage, false);
    } else if (page !== 1) {
      // occurs on back + forward history
      await this.getPinsFromAPI(1, false);
    }
  };

  handleClickOlder = async (event?: React.MouseEvent) => {
    const { page, maxPage } = this.state;
    if (event) {
      event.preventDefault();
    }
    if (page >= maxPage) {
      return;
    }

    await this.getPinsFromAPI(page + 1);
  };

  handleClickNewer = async (event?: React.MouseEvent) => {
    const { page } = this.state;
    if (event) {
      event.preventDefault();
    }
    if (page === 1) {
      return;
    }

    await this.getPinsFromAPI(page - 1);
  };

  getPinsFromAPI = async (page: number, pushHistory: boolean = true) => {
    const { newAlert, user } = this.props;
    const { APIService } = this.context;
    this.setState({ loading: true });

    try {
      const limit = (page - 1) * this.DEFAULT_PINS_PER_PAGE;
      const count = this.DEFAULT_PINS_PER_PAGE;
      const newPins = await APIService.getPinsForUser(user.name, limit, count);

      if (!newPins.pinned_recordings.length) {
        // No pins were fetched
        this.setState({ loading: false });
        return;
      }

      const totalCount = parseInt(newPins.total_count, 10);
      this.setState({
        loading: false,
        page,
        maxPage: Math.ceil(totalCount / this.DEFAULT_PINS_PER_PAGE),
        pins: newPins.pinned_recordings,
      });
      if (pushHistory) {
        window.history.pushState(null, "", `?page=${[page]}`);
      }

      // Scroll window back to the top of the events container element
      const eventContainerElement = document.querySelector(
        "#pinned-recordings"
      );
      if (eventContainerElement) {
        eventContainerElement.scrollIntoView({ behavior: "smooth" });
      }
    } catch (error) {
      newAlert(
        "warning",
        "Could not load pin history",
        <>
          Something went wrong when we tried to load your pinned recordings,
          please try again or contact us if the problem persists.
          <br />
          <strong>
            {error.name}: {error.message}
          </strong>
        </>
      );
      this.setState({ loading: false });
    }
  };

  // BrainzPlayer functions
  removePinFromPinsList = (pin: PinnedRecording) => {
    const { pins } = this.state;
    const index = pins.indexOf(pin);

    pins.splice(index, 1);
    this.setState({ pins });
  };

  render() {
    const { user, profileUrl, newAlert } = this.props;
    const { pins, page, direction, loading, maxPage } = this.state;
    const { currentUser } = this.context;

    const isNewerButtonDisabled = page === 1;
    const isOlderButtonDisabled = page >= maxPage;

    const pinsAsListens = pins.map((pin) => {
      return getListenablePin(pin);
    });

    return (
      <div role="main">
        <div className="row">
          <div className="col-md-8">
            <h3>Pinned Recordings</h3>

            {pins.length === 0 && (
              <>
                <div className="lead text-center">No pins yet</div>

                {user.name === currentUser.name && (
                  <>
                    Pin one of your
                    <a href={`${profileUrl}`}> recent Listens!</a>
                  </>
                )}
              </>
            )}

            {pins.length > 0 && (
              <div>
                <div
                  style={{
                    height: 0,
                    position: "sticky",
                    top: "50%",
                    zIndex: 1,
                  }}
                >
                  <Loader isLoading={loading} />
                </div>
                <div
                  id="pinned-recordings"
                  style={{ opacity: loading ? "0.4" : "1" }}
                >
                  {pins?.map((pin) => {
                    return (
                      <PinnedRecordingCard
                        key={`${pin.created}-${pin.track_metadata.track_name}-${pin.recording_msid}-${user}`}
                        userName={user.name}
                        pinnedRecording={pin}
                        isCurrentUser={currentUser?.name === user?.name}
                        removePinFromPinsList={this.removePinFromPinsList}
                        newAlert={newAlert}
                      />
                    );
                  })}

                  {pins.length < this.DEFAULT_PINS_PER_PAGE && (
                    <h5 className="text-center">No more pins to show.</h5>
                  )}
                </div>

                <ul
                  className="pager"
                  id="navigation"
                  style={{ marginRight: "-1em", marginLeft: "1.5em" }}
                >
                  <li
                    className={`previous ${
                      isNewerButtonDisabled ? "disabled" : ""
                    }`}
                  >
                    <a
                      role="button"
                      onClick={this.handleClickNewer}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") this.handleClickNewer();
                      }}
                      tabIndex={0}
                      href={
                        isNewerButtonDisabled ? undefined : `?page=${page - 1}`
                      }
                    >
                      &larr; Newer
                    </a>
                  </li>
                  <li
                    className={`next ${
                      isOlderButtonDisabled ? "disabled" : ""
                    }`}
                    style={{ marginLeft: "auto" }}
                  >
                    <a
                      role="button"
                      onClick={this.handleClickOlder}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") this.handleClickOlder();
                      }}
                      tabIndex={0}
                      href={
                        isOlderButtonDisabled ? undefined : `?page=${page + 1}`
                      }
                    >
                      Older &rarr;
                    </a>
                  </li>
                </ul>
              </div>
            )}
          </div>
          <div
            className="col-md-4"
            // @ts-ignore
            // eslint-disable-next-line no-dupe-keys
            style={{ position: "-webkit-sticky", position: "sticky", top: 20 }}
          >
            <BrainzPlayer
              direction={direction}
              listens={pinsAsListens}
              newAlert={newAlert}
            />
          </div>
        </div>
      </div>
    );
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const { domContainer, reactProps, globalReactProps } = getPageProps();
  const { api_url, current_user, spotify, youtube } = globalReactProps;
  const { user, pins, total_count, profile_url } = reactProps;

  const apiService = new APIServiceClass(
    api_url || `${window.location.origin}/1`
  );

  const UserPinsWithAlertNotifications = withAlertNotifications(UserPins);

  const globalProps: GlobalAppContextT = {
    APIService: apiService,
    currentUser: current_user,
    spotifyAuth: spotify,
    youtubeAuth: youtube,
  };

  ReactDOM.render(
    <ErrorBoundary>
      <GlobalAppContext.Provider value={globalProps}>
        <UserPinsWithAlertNotifications
          user={user}
          pins={pins}
          totalCount={total_count}
          profileUrl={profile_url}
        />
      </GlobalAppContext.Provider>
    </ErrorBoundary>,
    domContainer
  );
});
