/**
Cast receiver app intended for playing local media.
*/


/*
 * Convenience variables to access the CastReceiverContext and PlayerManager.
 */
const context = cast.framework.CastReceiverContext.getInstance();
const playerManager = context.getPlayerManager();

/**
 * Debug Logger
 */
const castDebugLogger = cast.debug.CastDebugLogger.getInstance();
const LOG_RECEIVER_TAG = 'Receiver';

/*
 * Uncomment below line to enable debug logger, show a 'DEBUG MODE' tag at
 * top left corner and show debug overlay.
 */
//  context.addEventListener(cast.framework.system.EventType.READY, () => {
//   if (!castDebugLogger.debugOverlayElement_) {
//     /**
//      *  Enable debug logger
//      */
//       castDebugLogger.setEnabled(true);

//     /**
//      * Show debug overlay.
//      */
//       castDebugLogger.showDebugLogs(true);
//   }
// });

/*
 * Set verbosity level for Core events.
 */
castDebugLogger.loggerLevelByEvents = {
  'cast.framework.events.category.CORE':          cast.framework.LoggerLevel.DEBUG,
  'cast.framework.events.EventType.MEDIA_STATUS': cast.framework.LoggerLevel.DEBUG
};

/*
 * Set verbosity level for custom tag.
 * Enables log messages for error, warn, info and debug.
 */
castDebugLogger.loggerLevelByTags = {
  LOG_RECEIVER_TAG: cast.framework.LoggerLevel.DEBUG
};

/*
 * Log errors on playerManager.
 */
playerManager.addEventListener(
  cast.framework.events.EventType.ERROR, (event) => {
    if (event) {
    castDebugLogger.error(LOG_RECEIVER_TAG,
      'Error occured. Detailed Error Code: ' + event.detailedErrorCode);
		}
});

/*
 * Apply metadata changes on the current queue item directly to the player
 */
playerManager.addEventListener(
  cast.framework.events.EventType.REQUEST_QUEUE_UPDATE, (event) => {
    let currentId = playerManager.getQueueManager().getCurrentItem().itemId;
    event.requestData.items.forEach((item) => {
      if (item.itemId == currentId)  {
        let mediaInformation = playerManager.getMediaInformation();
        mediaInformation.metadata = item.media.metadata;
        playerManager.setMediaInformation(mediaInformation);
      }
    });
});


/*
 * Configure the CastReceiverOptions.
 */
const castReceiverOptions = new cast.framework.CastReceiverOptions();

/*
 * Set the player configuration.
 */
const playbackConfig = new cast.framework.PlaybackConfig();
playbackConfig.autoResumeDuration = 1;
castReceiverOptions.playbackConfig = playbackConfig;
castDebugLogger.info(LOG_RECEIVER_TAG,
  `autoResumeDuration set to: ${playbackConfig.autoResumeDuration}`);

/* 
 * Set the SupportedMediaCommands.
 */
castReceiverOptions.supportedCommands =
  cast.framework.messages.Command.ALL_BASIC_MEDIA |
  cast.framework.messages.Command.STREAM_TRANSFER

context.start(castReceiverOptions);
