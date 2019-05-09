To get started, enter the Notebooks section and open the README notebook 
# sample.wikirecent
## Tutorials of live processing of Wikipedia recent updates feed using ICP4D. 

### Wikipedia provides a realtime feed of recent updates to it's content. 
#### These tutorials demonstrate processing this live data using ICP4D, processing the data in the following phases:


- Separate 'robot' updates from human updates.
- extract updates with pertaining to images
- analyse extracted images for faces, extract cropped faces
- score cropped images using emotional analysis   

Resulting in realtime categorization of content submitted to Wikiepedia rendered in Juypter notebooks 
as illustrated by:
![](icpWiki4.gif)

This repository contains examples and tutorials of live processing using this feed.


## Juypter Notebooks extracts - details


Example of utilizing data derived solely from the feed, a dashboard snapshot 
showing top editors, articles and languages of updates in the last 30 seconds.
Refer to imgAna_2 notebook for details. 

![](topLangUserTitle.png)


Example of integrating the ['Facial Recognizer'](https://developer.ibm.com/exchanges/models/all/max-facial-recognizer/) into the Streams application . The Streams 
application is extracting the images submitted to Wikipedia, in this case someone submitted a classic movie poster. The image was run through the 'Facial Emotion Classfier'
and results rendered in a notebook where this still was captured. Refer to imgAna_4 notebook for details.

![](facialLocation.jpg)

Example of using ['Facial Recognizer'](https://developer.ibm.com/exchanges/models/all/max-facial-recognizer/) 
in conjuntion with ['Facial Emotion Classifier'](https://developer.ibm.com/exchanges/models/all/max-facial-emotion-classifier/). The Streams
application extracts faces from images submitted to Wikipedia via the 'Facial Recognizer'. Streams pushes the face images to the 'Factial Emotion Classifier' 
for analysis, the results of which are rendered in a notebook where this still was captured. Refer to imgAna_4 notebook for details.
The emotions are rendered as pie chart here, when an emotion analysis does not return score the scale is displayed. 

![](imgClassify.jpg)

### Notes
- Notebooks are functional (Cloud & ICP4D) make them consumable for ICP4D.
- At this moment the goal is to have each notebook be standalone, all components to within the notebook. This may not be practical since notebook use
a significant portion of the previous notebook. 

 Below is a capture of Streams application graph executing imgAna_4, numbers attached to connectors indicate message flow in the last seconds.
![](wikirecentFlow.gif)
